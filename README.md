# 🎮 Jogo das 5 Palavras

Um jogo multiplayer online onde os jogadores devem adivinhar as palavras uns dos outros!

## 🚀 Como fazer Deploy no Render

### Passo 1: Preparar o Repositório

1. **Criar conta no GitHub** (se não tiver):
   - Acesse [github.com](https://github.com)
   - Clique em "Sign up" e crie sua conta

2. **Criar um novo repositório**:
   - Clique no botão "+" no canto superior direito
   - Selecione "New repository"
   - Nome: `jogo-5-palavras` (ou outro nome de sua escolha)
   - Marque como "Public"
   - Clique em "Create repository"

3. **Fazer upload dos arquivos**:
   - Na página do repositório criado, clique em "uploading an existing file"
   - Arraste todos os arquivos da pasta "Jogo das 5 Palavras" para o GitHub
   - Escreva uma mensagem como "Initial commit"
   - Clique em "Commit changes"

### Passo 2: Deploy no Render

1. **Criar conta no Render**:
   - Acesse [render.com](https://render.com)
   - Clique em "Get Started for Free"
   - Conecte com sua conta do GitHub

2. **Criar novo Web Service**:
   - No dashboard do Render, clique em "New +"
   - Selecione "Web Service"
   - Conecte seu repositório GitHub
   - Selecione o repositório `jogo-5-palavras`

3. **Configurar o serviço**:
   - **Name**: `jogo-5-palavras` (ou outro nome)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -c gunicorn.conf.py app:app`
   - **Plan**: Selecione "Free" (gratuito)

4. **Deploy**:
   - Clique em "Create Web Service"
   - Aguarde o deploy (pode levar alguns minutos)
   - Quando terminar, você receberá uma URL como: `https://jogo-5-palavras.onrender.com`

### Passo 3: Testar o Jogo

1. Acesse a URL fornecida pelo Render
2. Crie uma sala de jogo
3. Compartilhe o código da sala com seus amigos
4. Divirtam-se jogando!

## 🎯 Como Jogar

1. **Criar/Entrar na Sala**: Um jogador cria a sala e compartilha o código
2. **Definir Palavras**: Cada jogador define suas 5 palavras secretas
3. **Adivinhar**: Os jogadores se revezam tentando adivinhar as palavras dos adversários
4. **Dicas Dinâmicas**: A cada erro, mais letras da palavra são reveladas
5. **Vitória**: Ganha quem descobrir todas as palavras do adversário primeiro!

## 📱 Recursos

- ✅ Multiplayer em tempo real
- ✅ Chat integrado
- ✅ Interface responsiva (funciona no celular)
- ✅ Dicas dinâmicas
- ✅ Histórico de tentativas
- ✅ Palavra de referência
- ✅ Design moderno e escuro

## 🔧 Tecnologias Utilizadas

- **Backend**: Python, Flask, Flask-SocketIO
- **Frontend**: HTML5, CSS3, JavaScript
- **Deploy**: Render.com
- **Comunicação**: WebSockets (Socket.IO)

## 📞 Suporte

Se tiver problemas com o deploy, verifique:

1. **Arquivos necessários**: Certifique-se de que todos os arquivos estão no GitHub
2. **requirements.txt**: Deve estar na raiz do projeto
3. **Logs do Render**: Verifique os logs na aba "Logs" do seu serviço
4. **Porta**: O Render define automaticamente a porta via variável `$PORT`

## 🎉 Pronto!

Agora você pode jogar com seus amigos de qualquer lugar do mundo! 🌍

Compartilhe a URL do seu jogo e divirtam-se! 🎮
