// Application state
let currentFile = null;
let isProcessing = false;
let processedData = null;
let currentJobId = null;
let progressInterval = null;

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileSelected = document.getElementById('fileSelected');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const processBtn = document.getElementById('processBtn');
const uploadSection = document.getElementById('uploadSection');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressLabel = document.getElementById('progressLabel');
const progressPercent = document.getElementById('progressPercent');
const progressSteps = document.getElementById('progressSteps');
const playerSection = document.getElementById('playerSection');
const videoPlayer = document.getElementById('videoPlayer');
const subtitleTrack = document.getElementById('subtitleTrack');
const toggleSubtitles = document.getElementById('toggleSubtitles');
const downloadSection = document.getElementById('downloadSection');
const resetSection = document.getElementById('resetSection');
const resetBtn = document.getElementById('resetBtn');
const notification = document.getElementById('notification');
const notificationText = document.getElementById('notificationText');
const csrftoken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

// Application data
const videoFormats = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'];

// Django Integration Functions
function getCookie(name) {
    // Primeiro tenta pegar da meta tag
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    if (metaToken && name === 'csrftoken') {
        return metaToken.getAttribute('content');
    }
    
    // Fallback para cookie
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

async function uploadVideo(file) {
    const formData = new FormData();
    formData.append('video_file', file);

    try {
        showNotification('Iniciando upload...', 'info');

        const response = await fetch('/api/upload/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrftoken,
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Erro no upload');
        }

        const data = await response.json();
        showNotification('Upload realizado com sucesso!', 'success');
        return data;

    } catch (error) {
        console.error('Erro no upload:', error);
        showNotification(`Erro no upload: ${error.message}`, 'error');
        throw error;
    }
}

async function checkProgress(jobId) {
    console.log("Verificando progresso para job:", jobId);
    
    try {
        const response = await fetch(`/api/progress/${jobId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            }
        });
        
        console.log("Response status:", response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log("📦 Dados brutos do backend:", data);
        
        // Mapear status Django para interface
        const statusMap = {
            'pending': { progress: 5, step: 'Na fila de processamento...', currentStep: 'upload' },
            'extracting': { progress: 25, step: 'Extraindo áudio do vídeo...', currentStep: 'extract' },
            'transcribing': { progress: 60, step: 'Transcrevendo com Whisper...', currentStep: 'transcribe' },
            'generating': { progress: 85, step: 'Gerando arquivos de legenda...', currentStep: 'generate' },
            'completed': { progress: 100, step: 'Processamento concluído!', currentStep: 'finalize' },
            'failed': { progress: 0, step: 'Erro no processamento', currentStep: 'error' }
        };
        
        const mapped = statusMap[data.status] || { 
            progress: data.progress || 0, 
            step: data.current_step || 'Processando...', 
            currentStep: 'upload' 
        };
        
        const result = {
            ...data,
            progress: mapped.progress,
            current_step: mapped.step,
            ui_step: mapped.currentStep,
            files: data.files || {}
        };
        
        console.log("Dados mapeados:", result);
        return result;
        
    } catch (error) {
        console.error('Erro detalhado na verificação:', error);
        throw error;
    }
}


async function downloadFile(type, jobId) {
    if (!jobId) {
        showNotification('ID do job não encontrado', 'error');
        return;
    }

    const endpoints = {
        'video': `/api/transcription/${jobId}/download_video/`,
        'srt': `/api/transcription/${jobId}/download_srt/`,
        'vtt': `/api/transcription/${jobId}/download_vtt/`,
        'transcript': `/api/transcription/${jobId}/download_transcript/`
    };

    const fileNames = {
        'video': 'video_com_legendas.mp4',
        'srt': 'legendas.srt',
        'vtt': 'legendas.vtt',
        'transcript': 'transcricao.txt'
    };

    try {
        const endpoint = endpoints[type];
        if (!endpoint) {
            throw new Error('Tipo de arquivo inválido');
        }

        showNotification(`Preparando download...`, 'info');

        const response = await fetch(endpoint, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken,
            }
        });

        if (!response.ok) {
            throw new Error('Arquivo não encontrado');
        }

        // Criar blob e download
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileNames[type];
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showNotification(`Download de ${fileNames[type]} iniciado!`, 'success');

    } catch (error) {
        console.error('Erro no download:', error);
        showNotification(`Erro no download: ${error.message}`, 'error');
    }
}

// Event Handlers
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelection(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFileSelection(file);
    }
}

function handleFileSelection(file) {
    if (!validateFile(file)) {
        showNotification('Formato de arquivo não suportado. Use: MP4, AVI, MOV, MKV, WEBM, FLV, WMV', 'error');
        return;
    }

    currentFile = file;
    displayFileInfo(file);
    showSection(fileSelected);
}

function validateFile(file) {
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    return videoFormats.includes(fileExtension);
}

function displayFileInfo(file) {
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function startProcessing() {
    if (!currentFile || isProcessing) return;

    isProcessing = true;
    processBtn.disabled = true;
    hideSection(uploadSection);
    showSection(progressSection);

    try {
        // Upload do arquivo
        console.log('Iniciando upload do vídeo:', currentFile.name);
        const uploadResult = await uploadVideo(currentFile);
        currentJobId = uploadResult.job_id;

        // Iniciar monitoramento de progresso
        console.log('currentJobId:', currentJobId)
        startProgressMonitoring();

    } catch (error) {
        isProcessing = false;
        processBtn.disabled = false;
        showSection(uploadSection);
        hideSection(progressSection);
        showNotification(`Erro: ${error.message}`, 'error');
    }
}

function startProgressMonitoring() {
    if (!currentJobId) return;

    progressInterval = setInterval(async () => {
        console.log("⏰ Checando progresso...", new Date().toISOString());
        
        try {
            const progressData = await checkProgress(currentJobId);
            console.log("Dados recebidos:", progressData);
            
            updateProgress(progressData);
            
            if (progressData.status === 'completed') {
                console.log("Job completado!");
                clearInterval(progressInterval);
                completeProcessing(progressData);
            } else if (progressData.status === 'failed') {
                console.log(" Job falhou!");
                clearInterval(progressInterval);
                handleProcessingError(progressData.current_step);
            }
            
        } catch (error) {
            console.error('Erro no monitoramento:', error);
            clearInterval(progressInterval);
            handleProcessingError('Erro na comunicação com servidor');
        }
    }, 2000);
}

function updateProgress(data) {
    // Atualizar barra de progresso
    progressFill.style.width = `${data.progress}%`;
    progressPercent.textContent = `${Math.round(data.progress)}%`;
    progressLabel.textContent = data.current_step;

    // Atualizar steps visuais
    updateProgressSteps(data.ui_step);
}

function updateProgressSteps(currentStep) {
    const steps = ['upload', 'extract', 'transcribe', 'generate', 'finalize'];
    const currentIndex = steps.indexOf(currentStep);

    steps.forEach((step, index) => {
        const stepElement = document.querySelector(`[data-step="${step}"]`);
        if (stepElement) {
            stepElement.classList.remove('active', 'completed');

            if (index < currentIndex) {
                stepElement.classList.add('completed');
            } else if (index === currentIndex) {
                stepElement.classList.add('active');
            }
        }
    });
}

function completeProcessing(data) {
    isProcessing = false;
    processedData = {
        jobId: currentJobId,
        files: data.files,
        originalFile: currentFile
    };

    // Setup video player se o vídeo estiver disponível
    if (data.files && data.files.video) {
        setupVideoPlayer(data.files.video, data.files.vtt);
    }

    // Mostrar seções de resultado
    hideSection(progressSection);
    if (data.files && data.files.video) {
        showSection(playerSection);
    }
    showSection(downloadSection);
    showSection(resetSection);
    showNotification('Processamento concluído com sucesso!', 'success');
}

function handleProcessingError(errorMessage) {
    isProcessing = false;
    processBtn.disabled = false;
    hideSection(progressSection);
    showSection(uploadSection);
    showNotification(`Erro no processamento: ${errorMessage}`, 'error');
}

function setupVideoPlayer(videoUrl, vttUrl) {
    videoPlayer.src = videoUrl;

    if (vttUrl) {
        subtitleTrack.src = vttUrl;
        // Desabilitar legendas por padrão
        videoPlayer.textTracks[0].mode = 'disabled';
        toggleSubtitles.innerHTML = '<i class="fas fa-closed-captioning"></i> Ativar Legendas';
    }
}

function toggleSubtitleTrack() {
    if (videoPlayer.textTracks.length === 0) return;

    const track = videoPlayer.textTracks[0];
    if (track.mode === 'showing') {
        track.mode = 'disabled';
        toggleSubtitles.innerHTML = '<i class="fas fa-closed-captioning"></i> Ativar Legendas';
        toggleSubtitles.classList.remove('btn--primary');
        toggleSubtitles.classList.add('btn--secondary');
    } else {
        track.mode = 'showing';
        toggleSubtitles.innerHTML = '<i class="fas fa-closed-captioning"></i> Desativar Legendas';
        toggleSubtitles.classList.remove('btn--secondary');
        toggleSubtitles.classList.add('btn--primary');
    }
}

// UI Helper Functions
function showSection(element) {
    element.style.display = 'block';
    element.style.opacity = '0';
    element.style.transform = 'translateY(20px)';

    // Force reflow
    element.offsetHeight;

    element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    element.style.opacity = '1';
    element.style.transform = 'translateY(0)';
}

function hideSection(element) {
    element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    element.style.opacity = '0';
    element.style.transform = 'translateY(-20px)';

    setTimeout(() => {
        element.style.display = 'none';
    }, 300);
}

function showNotification(message, type = 'success') {
    notificationText.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';

    // Auto hide após 4 segundos
    setTimeout(() => {
        notification.style.display = 'none';
    }, 4000);
}

function resetApplication() {
    // Limpar intervalos
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }

    // Reset state
    currentFile = null;
    isProcessing = false;
    processedData = null;
    currentJobId = null;

    // Reset UI
    fileInput.value = '';
    processBtn.disabled = false;

    // Reset progress
    progressFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressLabel.textContent = 'Preparando...';

    // Reset steps
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active', 'completed');
    });
    const uploadStep = document.querySelector('[data-step="upload"]');
    if (uploadStep) {
        uploadStep.classList.add('active');
    }

    // Reset video player
    if (videoPlayer.src) {
        URL.revokeObjectURL(videoPlayer.src);
        videoPlayer.src = '';
    }

    if (subtitleTrack.src) {
        URL.revokeObjectURL(subtitleTrack.src);
        subtitleTrack.src = '';
    }

    // Show/hide sections
    showSection(uploadSection);
    hideSection(fileSelected);
    hideSection(progressSection);
    hideSection(playerSection);
    hideSection(downloadSection);
    hideSection(resetSection);

    // Reset subtitle button
    toggleSubtitles.innerHTML = '<i class="fas fa-closed-captioning"></i> Ativar Legendas';
    toggleSubtitles.classList.remove('btn--primary');
    toggleSubtitles.classList.add('btn--secondary');
}

// Event Listeners Setup
function setupEventListeners() {
    // Upload area events
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);

    // File input change
    fileInput.addEventListener('change', handleFileSelect);

    // Process button
    processBtn.addEventListener('click', startProcessing);

    // Video controls
    toggleSubtitles.addEventListener('click', toggleSubtitleTrack);

    // Download buttons - usando closure para passar currentJobId
    document.getElementById('downloadVideo').addEventListener('click', () => {
        if (processedData && processedData.jobId) {
            downloadFile('video', processedData.jobId);
        }
    });

    document.getElementById('downloadSrt').addEventListener('click', () => {
        if (processedData && processedData.jobId) {
            downloadFile('srt', processedData.jobId);
        }
    });

    document.getElementById('downloadVtt').addEventListener('click', () => {
        if (processedData && processedData.jobId) {
            downloadFile('vtt', processedData.jobId);
        }
    });

    document.getElementById('downloadTranscript').addEventListener('click', () => {
        if (processedData && processedData.jobId) {
            downloadFile('transcript', processedData.jobId);
        }
    });

    // Reset button
    resetBtn.addEventListener('click', resetApplication);
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function () {
    setupEventListeners();
    resetApplication();
});

// Cleanup function for URLs
window.addEventListener('beforeunload', function () {
    if (progressInterval) {
        clearInterval(progressInterval);
    }

    if (processedData) {
        if (processedData.videoUrl) URL.revokeObjectURL(processedData.videoUrl);
        if (processedData.subtitleUrl) URL.revokeObjectURL(processedData.subtitleUrl);
    }
});
