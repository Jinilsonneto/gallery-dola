   IMAGE DOWNLOADER - Anti-Bot Edition v3
   Tutorial de Instalacao e Uso

SOBRE O PROGRAMA
----------------
Baixa automaticamente todas as imagens de qualquer pagina web,
simulando comportamento humano para contornar protecoes anti-bot
e Cloudflare. Versao 3.0 com melhorias significativas:

NOVIDADES NA VERSAO 3:
- Deteccao de duplicatas por hash MD5
- Filtro automatico de anuncios e trackers
- Barra de progresso visual (com tqdm)
- Backoff exponencial para retries
- Validacao robusta de imagens (tamanho e dimensoes)
- Suporte a mais formatos (.avif, .svg)
- Extracao de meta tags (Open Graph, Twitter Cards)
- Opcao para respeitar robots.txt
- CLI aprimorada com mais opcoes
- Logging estruturado e relatorio detalhado


PRE-REQUISITOS


- Python 3.8 ou superior instalado
- pip (gerenciador de pacotes do Python)

Para verificar se voce tem Python instalado, abra o terminal e digite:

    python --version
    ou
    python3 --version


INSTALACAO DAS DEPENDENCIAS

Instale as bibliotecas necessarias com o comando abaixo:

    pip install cloudscraper beautifulsoup4 Pillow tqdm --break-system-packages

Descricao de cada biblioteca:
  - cloudscraper   : Contorna protecoes Cloudflare e anti-bot
  - beautifulsoup4 : Faz a leitura e analise do HTML da pagina
  - Pillow         : Verifica as dimensoes das imagens baixadas
  - tqdm           : Barra de progresso visual (opcional, mas recomendado)

Se o comando pip nao funcionar, tente:

    pip3 install cloudscraper beautifulsoup4 Pillow tqdm --break-system-packages


COMO USAR


1. MODO INTERATIVO (mais facil)
--------------------------------
Basta rodar o script sem argumentos. O programa vai pedir a URL:

    python Gallery-dola.py

Exemplo de sessao:
    > Digite a URL da pagina: https://exemplo.com/galeria
    O programa vai baixar todas as imagens automaticamente.


2. MODO POR LINHA DE COMANDO
------------------------------
Passe a URL diretamente como argumento:

    python Gallery-dola.py https://exemplo.com/galeria


3. COM OPCOES AVANCADAS
------------------------
Voce pode personalizar o comportamento com as flags abaixo:

    python Gallery-dola.py <URL> [opcoes]

    Opcoes disponíveis:

    -o, --output <pasta>
        Define a pasta onde as imagens serao salvas.
        Padrao: downloads
        Exemplo: -o minhas_fotos

    -W, --min-width <pixels>
        Largura minima para baixar a imagem (ignora imagens menores).
        Padrao: 100
        Exemplo: -W 500

    -H, --min-height <pixels>
        Altura minima para baixar a imagem (ignora imagens menores).
        Padrao: 100
        Exemplo: -H 500

    --max-size <MB>
        Tamanho maximo do arquivo em megabytes.
        Padrao: 50
        Exemplo: --max-size 100

    --logos
        Por padrao, logos e icones sao ignorados automaticamente.
        Use esta flag para incluí-los no download.
        Exemplo: --logos

    --ads
        Inclui anuncios e banners (padrao: ignora).
        Exemplo: --ads

    --duplicates
        Baixa imagens duplicadas (padrao: ignora repetidas).
        Exemplo: --duplicates

    --no-validate
        Nao valida dimensoes das imagens (baixa qualquer tamanho).
        Exemplo: --no-validate

    --robots
        Respeita regras do robots.txt (padrao: ignora).
        Exemplo: --robots

    --delay-min <segundos>
        Tempo minimo de espera entre cada download (simula humano).
        Padrao: 1.5
        Exemplo: --delay-min 2.0

    --delay-max <segundos>
        Tempo maximo de espera entre cada download.
        Padrao: 4.0
        Exemplo: --delay-max 6.0

    --retries <numero>
        Numero maximo de tentativas para downloads falhos.
        Padrao: 3
        Exemplo: --retries 5

    --timeout <segundos>
        Timeout para requisicoes HTTP.
        Padrao: 30
        Exemplo: --timeout 60


EXEMPLOS PRATICOS


Baixar imagens de uma galeria com configuracoes padrao:
    python Gallery-dola.py https://site.com/galeria

Salvar em pasta personalizada:
    python Gallery-dola.py https://site.com/galeria -o fotos_baixadas

Baixar apenas imagens grandes (minimo 800x600):
    python Gallery-dola.py https://site.com/galeria -W 800 -H 600

Incluir logos e ser mais cauteloso (delays maiores):
    python Gallery-dola.py https://site.com/galeria --logos --delay-min 3 --delay-max 8

Ignorar robots.txt e baixar tudo incluindo anuncios:
    python Gallery-dola.py https://site.com/galeria --ads --robots

Combinando varias opcoes:
    python Gallery-dola.py https://site.com/galeria -o resultado -W 400 -H 400 --delay-min 2 --max-size 100



ONDE FICAM AS IMAGENS BAIXADAS


As imagens sao salvas em:

    downloads/<nome-do-site>/

Exemplo: ao baixar de "https://exemplo.com/galeria", as imagens
ficam em:

    downloads/exemplo.com_galeria/
        001_foto-de-praia.jpg
        002_paisagem.png
        003_a1b2c3d4.webp   <- nome gerado automaticamente quando
                               a imagem nao tem descricao (alt)

Ao final de cada execucao, o programa exibe um resumo detalhado:
    - Tempo decorrido
    - Quantidade de imagens baixadas com sucesso
    - Quantidade de imagens puladas (tamanho inadequado)
    - Quantidade de duplicatas detectadas
    - Quantidade de falhas
    - Total processado
    - Caminho completo da pasta de destino


RESOLUCAO DE PROBLEMAS


ERRO: "Dependencias faltando"
    Solucao: Rode o comando de instalacao novamente:
    pip install cloudscraper beautifulsoup4 Pillow tqdm --break-system-packages

ERRO: "Nao foi possivel acessar a pagina"
    - Verifique se a URL esta correta e acessível no navegador.
    - Alguns sites bloqueiam downloads automatizados mesmo com
      cloudscraper. Tente aumentar os delays (--delay-min, --delay-max).
    - Aumente o timeout: --timeout 60

POUCAS IMAGENS ENCONTRADAS
    - O site pode usar JavaScript para carregar imagens dinamicamente
      (SPA/React/Vue). Este programa analisa apenas o HTML estatico.
    - Tente aumentar o filtro de tamanho minimo (-W, -H) para verificar
      se imagens existem porem estao sendo filtradas por tamanho.
    - Verifique se as opcoes --logos ou --ads nao estao filtrando
      conteudo que voce deseja.

IMAGENS COM NOMES ESTRANHOS (sequencias de letras e numeros)
    - Isso e normal. Ocorre quando a imagem nao possui texto descritivo
      (atributo alt) no HTML. O nome e gerado a partir do endereco da imagem.

MUITAS DUPLICATAS
    - O programa detecta duplicatas automaticamente por hash MD5.
    - Use --duplicates se quiser baixar todas mesmo assim.


OBSERVACOES IMPORTANTES


- Use este programa apenas em sites que permitem scraping ou cujo
  conteudo seja de sua propriedade. Respeite os Termos de Uso de
  cada site e a legislacao de direitos autorais aplicavel.

- O programa simula comportamento humano com delays aleatorios para
  nao sobrecarregar os servidores. Nao reduza os delays para valores
  muito baixos.

- Formatos suportados: .jpg, .jpeg, .png, .webp, .gif, .bmp, .tiff, .avif, .svg

- Para ver todas as opcoes disponiveis, use:
    python Gallery-dola.py --help


ESTRUTURA DO PROJETO

    Gallery-dola.py    <- Script principal (unico arquivo necessario)
    README.md          <- Este arquivo com instrucoes
    downloads/         <- Pasta criada automaticamente ao baixar
    

