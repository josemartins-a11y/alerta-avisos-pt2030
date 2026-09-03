# Alerta de novos avisos — Portugal 2030

Verifica https://portugal2030.pt/avisos/ três vezes por dia (08h, 13h, 18h,
hora de Lisboa) e envia um email quando aparecem avisos novos.

## Nota sobre seletores de HTML

A página de avisos carrega o conteúdo via JavaScript. O script apanha,
de forma genérica, todos os links que apontam para /avisos/. Se quiseres
afinar isto, corre localmente com DEBUG_DUMP_HTML=1 para gerar
debug_page.html e ajustarmos os seletores.

## Manutenção

O GitHub desativa workflows agendados ao fim de 60 dias sem atividade —
mas como este workflow faz commit do estado a cada execução, mantém-se
sempre ativo sozinho.
