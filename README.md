# 🎮 Corrente Verbal

Um jogo multiplayer online onde os jogadores devem adivinhar as palavras uns dos outros.

## 🚀 Deploy no Render (passo a passo)

1) Preparar o repositório
- Suba este projeto para um repositório público no GitHub.

2) Criar o serviço
- Entre em https://render.com e conecte sua conta do GitHub.
- Clique em New → Web Service.
- Selecione o seu repositório.
- Configure:
  - Name: corrente-verbal (ou outro)
  - Environment: Python 3
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `gunicorn -c gunicorn.conf.py app:app`
  - Plan: Free (ou superior)
- Crie o serviço e aguarde o deploy.

3) Variáveis e saúde
- Já configurado em `render.yaml`:
  - healthCheckPath: `/health`
  - WEB_CONCURRENCY: `1` (plano gratuito)
  - RENDER: `1` (ativa modo produção no app)
  - PYTHON_VERSION: `3.9.16`

4) Testar
- Acesse a URL que o Render fornecer (ex.: https://corrente-verbal.onrender.com).
- Crie uma sala, entre em outra aba como segundo jogador e jogue.

## 📦 Tecnologias
- Backend: Flask + Flask-SocketIO (WebSockets via gevent)
- Servidor: Gunicorn + Gevent WebSocket Worker
- Frontend: HTML, JavaScript, Tailwind CSS (via CDN) e CSS próprio (`static/style.css`)
- Healthcheck: `/health` e `/health/detailed`

## 🧩 Tailwind CSS
- Este projeto usa o CDN do Tailwind — não é necessário instalar pacotes Node nem alterar `requirements.txt`.
- Se preferir performance máxima em produção, faça build com Node (Tailwind + PostCSS) e referencie o CSS compilado em vez do CDN.

## 🕹️ Como Jogar (instruções iniciais)
1. Um jogador cria a sala e compartilha o código com os amigos.
2. Todos entram na sala com seus nomes.
3. O criador marca o modo de jogo (quando disponível) e aguarda os jogadores marcarem-se como prontos.
4. Quando todos (exceto o criador) estiverem prontos, o criador clica em “Iniciar Partida”.

5. Cada jogador define suas palavras secretas.
6. O jogo começa com turnos: você tenta adivinhar as palavras do seu alvo na ordem (1, depois 2, etc.).
7. A cada erro, mais uma letra da palavra atual é revelada como dica.
8. Vence quem descobrir todas as palavras do seu alvo primeiro. O gabarito pode ser exibido ao final.

Dicas:
- Use o chat para interagir com os outros jogadores.
- Reações por emoji estão disponíveis durante a partida.
- O criador pode transferir a liderança para outro jogador, se necessário.
- Se a conexão cair, o jogo tentará reconectar automaticamente.

## ⚙️ Ambiente de produção
- O `gunicorn.conf.py` já está preparado para WebSockets (GeventWebSocketWorker).
- O `app.py` habilita async_mode gevent quando a variável `RENDER` está definida.
- Mantenha apenas 1 worker no plano gratuito para evitar problemas com sessões em memória.

## ❗ Solução de problemas
- Erro de WebSocket: confirme que o worker do Gunicorn é `geventwebsocket.gunicorn.workers.GeventWebSocketWorker`.
- Reconexões constantes: verifique logs e o healthcheck `/health`.
- Página não abre: veja os logs do Render na aba Logs e confirme `requirements.txt` na raiz.
- Lerdeza no primeiro acesso: o plano Free hiberna. Aguarde alguns segundos.

## 📄 Licença
Uso livre para fins educacionais e pessoais. Ajuste conforme sua necessidade.
