# Front em templates Django com JS puro, sem passo de build

As telas são templates Django com JavaScript em módulos ES nativos e CSS puro, sem React, bundler nem npm. São poucas telas, e sem build o app fica mais simples de baixar, rodar e manter. Os dados vindos da API são inseridos na página com `textContent`/`createElement`, nunca com `innerHTML`. A validação fica no backend, com serializers do DRF.
