import os
import subprocess
import whisper
from pathlib import Path
from django.core.files.base import ContentFile
from django.core.files import File
import json
from loguru import logger


class VideoProcessor:
    def __init__(self, job):
        self.job = job
        self.error_message = None

    def update_progress(self, percentage: int, step: str) -> None:
        self.job.progress_percentage = percentage
        self.job.current_step = step
        self.job.save()
        logger.info(f"[{self.job.id}] Progress: {percentage}% - {step}")

    def has_audio_stream(self, path: str) -> bool:
        """Verifica, via ffprobe, se o arquivo possui alguma faixa de áudio.

        Vídeos baixados de streams (DASH) costumam trazer apenas a faixa de
        vídeo; nesses casos não há áudio para o Whisper transcrever.
        """
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=index", "-of", "csv=p=0", path],
                check=True, capture_output=True, text=True,
            )
            return bool(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Em caso de dúvida, deixa o ffmpeg tentar normalmente.
            return True

    def extract_audio(self) -> bool:
        self.update_progress(20, 'Extraindo o áudio do vídeo…')
        video_path = self.job.video_file.path

        if not self.has_audio_stream(video_path):
            self.error_message = (
                'O vídeo não possui faixa de áudio, então não há o que '
                'transcrever. Envie um vídeo com áudio.'
            )
            logger.error(f"[{self.job.id}] No audio stream found in '{video_path}'.")
            return False

        audio_path = f"{video_path}_temp.wav"
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path
        ]
        logger.info(f"[{self.job.id}] Running command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            with open(audio_path, 'rb') as audio_file:
                self.job.audio_file.save(
                    f"{self.job.id}_audio.wav",
                    File(audio_file)
                )
            Path(audio_path).unlink()
            logger.success(f"[{self.job.id}] Audio extracted successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[{self.job.id}] Audio extraction error: {e}")
            self.error_message = (
                'Não foi possível extrair o áudio deste vídeo. Verifique se o '
                'arquivo não está corrompido e tente novamente.'
            )
            return False

    def transcribe_audio(self):
        """Transcreve o audio salvando os trechos progressivamente.

        O audio e dividido em janelas de 30s (mesmo tamanho da janela interna
        do Whisper). A cada janela os trechos sao gravados no banco, o que
        permite ao frontend exibir as legendas em tempo real enquanto o video
        ainda esta sendo processado.
        """
        self.update_progress(60, 'Transcrevendo com Whisper…')
        from .models import SubtitleSegment
        try:
            logger.info(f"[{self.job.id}] Loading Whisper model...")
            model_name = os.getenv('WHISPER_MODEL', 'small')
            logger.info(f"[{self.job.id}] Model: {model_name}")
            model = whisper.load_model(model_name)

            logger.info(f"[{self.job.id}] Loading audio '{self.job.audio_file.path}'")
            audio = whisper.load_audio(self.job.audio_file.path)
            sample_rate = whisper.audio.SAMPLE_RATE
            total_samples = len(audio)
            total_seconds = total_samples / sample_rate

            self.job.duration_seconds = total_seconds
            self.job.save(update_fields=['duration_seconds'])

            chunk_seconds = 30
            chunk_size = chunk_seconds * sample_rate
            context_prompt = None
            offset = 0
            created = 0

            # Idioma: escolha do usuário -> variável de ambiente -> automático.
            language = (self.job.language or os.getenv('WHISPER_LANGUAGE', 'auto') or 'auto').strip().lower()
            if language in ('auto', 'none', 'detect'):
                language = None
            logger.info(f"[{self.job.id}] Language: {language or 'auto'}")

            # No modo automático, detecta o idioma somando as probabilidades de
            # várias janelas iniciais. Olhar só a primeira janela é frágil em
            # vídeos que misturam idiomas (ex.: narração em PT com trechos em EN).
            if language is None:
                try:
                    total_windows = max(1, int(total_seconds // chunk_seconds))
                    sample_windows = min(4, total_windows)
                    aggregate = {}
                    for w in range(sample_windows):
                        start = w * chunk_size
                        if start >= total_samples:
                            break
                        window = audio[start:start + chunk_size]
                        if len(window) < chunk_size:
                            window = whisper.pad_or_trim(window)
                        mel = whisper.log_mel_spectrogram(window).to(model.device)
                        _, probs = model.detect_language(mel)
                        for code, prob in probs.items():
                            aggregate[code] = aggregate.get(code, 0.0) + prob
                    if aggregate:
                        language = max(aggregate, key=aggregate.get)
                        self.job.language = language
                        self.job.save(update_fields=['language'])
                        logger.info(f"[{self.job.id}] Detected language: {language}")
                except Exception as exc:
                    logger.warning(f"[{self.job.id}] Language detection failed: {exc}")

            while offset < total_samples:
                chunk = audio[offset:offset + chunk_size]
                result = model.transcribe(
                    chunk,
                    language=language,
                    condition_on_previous_text=True,
                    initial_prompt=context_prompt,
                    verbose=False,
                )

                # Fallback: se ainda não sabemos o idioma, usa o da 1ª janela.
                if language is None:
                    detected = result.get('language')
                    if detected:
                        language = detected
                        self.job.language = detected
                        self.job.save(update_fields=['language'])
                        logger.info(f"[{self.job.id}] Detected language: {detected}")

                base = offset / sample_rate
                for segment in result.get("segments", []):
                    text = (segment.get("text") or "").strip()
                    if not text:
                        continue
                    SubtitleSegment.objects.create(
                        job=self.job,
                        start_time=base + segment.get("start", 0.0),
                        end_time=base + segment.get("end", 0.0),
                        text=text,
                        confidence=segment.get("confidence"),
                    )
                    created += 1

                # mantem um pouco de contexto para a proxima janela
                tail = (result.get("text") or "").strip()
                if tail:
                    context_prompt = tail[-200:]

                offset += chunk_size
                fraction = min(1.0, offset / total_samples)
                percent = 60 + int(fraction * 20)  # 60 -> 80
                self.update_progress(percent, 'Transcrevendo com Whisper…')

            logger.success(f"[{self.job.id}] Transcription completed ({created} segments).")
            return True
        except Exception as e:
            logger.error(f"[{self.job.id}] Transcription error: {e}")
            return None

    def generate_subtitle_files(self) -> None:
        self.update_progress(80, 'Gerando os arquivos de legenda…')
        logger.info(f"[{self.job.id}] Generating subtitle files...")

        segments = [seg for seg in self.job.segments.all() if seg.text and seg.text.strip()]
        logger.info(f"[{self.job.id}] {len(segments)} non-silent segments will be used for subtitles.")

        srt_content = self._generate_srt(segments)
        srt_file = ContentFile(srt_content.encode('utf-8'))
        self.job.srt_file.save(f"{self.job.id}.srt", srt_file)
        logger.success(f"[{self.job.id}] SRT file generated.")

        vtt_content = self._generate_vtt(segments)
        vtt_file = ContentFile(vtt_content.encode('utf-8'))
        self.job.vtt_file.save(f"{self.job.id}.vtt", vtt_file)
        logger.success(f"[{self.job.id}] VTT file generated.")

        json_data = [
            {
                'start': seg.start_time,
                'end': seg.end_time,
                'text': seg.text,
                'confidence': seg.confidence
            }
            for seg in segments
        ]
        json_content = json.dumps(json_data, indent=2, ensure_ascii=False)
        json_file = ContentFile(json_content.encode('utf-8'))
        self.job.json_file.save(f"{self.job.id}.json", json_file)
        logger.success(f"[{self.job.id}] JSON file generated.")

        txt_content = '\n'.join([seg.text for seg in segments])
        txt_file = ContentFile(txt_content.encode('utf-8'))
        self.job.transcript_file.save(f"{self.job.id}_transcript.txt", txt_file)
        logger.success(f"[{self.job.id}] TXT transcript generated.")

    def _generate_srt(self, segments) -> str:
        srt_lines = []
        idx = 1
        for seg in segments:
            if not seg.text or not seg.text.strip():
                continue
            start = self._format_srt_timestamp(seg.start_time)
            end = self._format_srt_timestamp(seg.end_time)
            srt_lines.append(f"{idx}\n{start} --> {end}\n{seg.text.strip()}\n")
            idx += 1
        return '\n'.join(srt_lines)

    def _generate_vtt(self, segments) -> str:
        vtt_lines = ["WEBVTT\n"]
        for seg in segments:
            if not seg.text or not seg.text.strip():
                continue
            start = self._format_vtt_timestamp(seg.start_time)
            end = self._format_vtt_timestamp(seg.end_time)
            vtt_lines.append(f"{start} --> {end}\n{seg.text.strip()}\n")
        return '\n'.join(vtt_lines)

    def _format_srt_timestamp(self, seconds: float) -> str:
        total_ms = round(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _format_vtt_timestamp(self, seconds: float) -> str:
        total_ms = round(seconds * 1000)
        h = total_ms // 3600000
        m = (total_ms % 3600000) // 60000
        s = (total_ms % 60000) // 1000
        ms = total_ms % 1000
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

    def mux_soft_subtitle(self) -> bool:
        self.update_progress(90, 'Montando o vídeo final…')
        video_path = self.job.video_file.path
        srt_path = self.job.srt_file.path
        output_path = f"{video_path}_with_subtitles.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", srt_path,
            "-c", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=por",
            output_path
        ]
        logger.info(f"[{self.job.id}] Running command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            with open(output_path, 'rb') as video_file:
                self.job.final_video.save(
                    f"{self.job.id}_with_subtitles.mp4",
                    File(video_file)
                )
            Path(output_path).unlink()
            logger.success(f"[{self.job.id}] Final video with soft subtitles muxed.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[{self.job.id}] Muxing error: {e}")
            return False

    def process(self) -> None:
        try:
            self.job.status = 'extracting'
            self.job.save()
            logger.info(f"[{self.job.id}] Starting audio extraction...")
            if not self.extract_audio():
                raise Exception(
                    self.error_message
                    or 'Não foi possível extrair o áudio do vídeo.'
                )
            self.job.status = 'transcribing'
            self.job.save()
            logger.info(f"[{self.job.id}] Starting audio transcription...")
            if not self.transcribe_audio():
                raise Exception('Falha ao transcrever o áudio do vídeo.')
            self.job.status = 'generating'
            self.job.save()
            logger.info(f"[{self.job.id}] Generating subtitle files...")
            self.generate_subtitle_files()
            logger.info(f"[{self.job.id}] Muxing final video...")
            self.mux_soft_subtitle()
            self.job.status = 'completed'
            self.job.progress_percentage = 100
            self.job.current_step = 'Transcrição concluída!'
            self.job.save()
            logger.success(f"[{self.job.id}] Pipeline completed successfully.")
        except Exception as e:
            self.job.status = 'failed'
            self.job.current_step = f'Erro: {str(e)}'
            self.job.save()
            logger.error(f"[{self.job.id}] Processing error: {e}")
