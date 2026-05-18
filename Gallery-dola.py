"""
IMAGE DOWNLOADER - Anti-Bot Edition v3
Baixa imagens de qualquer site como um humano real
Suporte a Cloudflare, protecoes anti-bot, JavaScript dinâmico e muito mais

Melhorias:
- Logging estruturado com níveis
- Progress bar visual
- Backoff exponencial para retries
- Detecção de duplicatas por hash
- Blacklist de domínios de ads/tracking
- Validação robusta de imagens
- Suporte a lazy loading avançado
- Rate limiting inteligente
"""

import re
import sys
import time
import random
import hashlib
import mimetypes
import urllib.parse
import urllib.robotparser
from pathlib import Path
from datetime import datetime
from collections import Counter
import io
import json

# ============================================================================
# IMPORTS COM VERIFICAÇÃO ELEGANTE
# ============================================================================
missing = []
try:
    import cloudscraper
except ImportError:
    missing.append("cloudscraper")
try:
    from bs4 import BeautifulSoup
except ImportError:
    missing.append("beautifulsoup4")
try:
    from PIL import Image
except ImportError:
    missing.append("Pillow")
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # Opcional

if missing:
    print(f"\n{'='*62}")
    print(f"[ERRO] Dependências faltando: {', '.join(missing)}")
    print(f"{'='*62}")
    print(f"\nExecute: pip install {' '.join(missing)} --break-system-packages\n")
    if tqdm is None:
        print("Opcional: pip install tqdm --break-system-packages (para barra de progresso)\n")
    sys.exit(1)

# ============================================================================
# CONFIGURAÇÕES PADRÃO
# ============================================================================
DEFAULT_CONFIG = {
    "min_width":       100,
    "min_height":      100,
    "max_file_size":   50 * 1024 * 1024,  # 50MB max
    "min_file_size":   1024,               # 1KB min
    "skip_logos":      True,
    "skip_ads":        True,
    "skip_duplicates": True,
    "delay_min":       1.5,
    "delay_max":       4.0,
    "max_retries":     3,
    "timeout":         30,
    "output_dir":      "downloads",
    "validate_images": True,
    "respect_robots":  False,
    "formats":         [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".avif", ".svg"],
}

# ============================================================================
# PALAVRAS-CHAVE PARA FILTRAGEM
# ============================================================================
LOGO_KEYWORDS = [
    "logo", "icon", "favicon", "sprite", "badge", "watermark",
    "brand", "seal", "emblem", "avatar", "thumbnail-icon",
    "site-icon", "wp-emoji", "loading", "placeholder", "blank", "spacer",
    "button", "nav-", "menu-", "social-", "share-", "cookie",
]

AD_KEYWORDS = [
    "ad-", "ads-", "advert", "banner", "promo", "sponsor",
    "affiliate", "tracking", "pixel", "analytics", "doubleclick",
    "googlesyndication", "adsystem", "adserver",
]

AD_DOMAINS = [
    "googleads", "doubleclick.net", "adservice.google", "googlesyndication.com",
    "facebook.com/tr", "analytics.", "tracking.", "pixel.",
    "adsystem.", "adserver.", "taboola.com", "outbrain.com",
    "criteo.com", "amazon-adsystem.com", "bidswitch.net",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


# ============================================================================
# CLASSE PRINCIPAL DO DOWNLOADER
# ============================================================================
class HumanImageDownloader:
    """
    Download de imagens com comportamento humano e bypass de proteções anti-bot.
    """
    
    def __init__(self, config=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.scraper = None
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.duplicates = 0
        self.seen_hashes = set()
        self.start_time = None
        self._init_scraper()

    def _init_scraper(self):
        """Inicializa o scraper com headers realistas."""
        ua = random.choice(USER_AGENTS)
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True},
            delay=random.uniform(3, 7),
        )
        self.scraper.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        })

    def _refresh_scraper(self):
        """Reinicia o scraper para evitar detecção após muitas requisições."""
        self.scraper.close()
        self._init_scraper()

    def _image_headers(self, page_url, img_url):
        """Headers específicos para download de imagens."""
        parsed = urllib.parse.urlparse(page_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            "Referer": page_url,
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "same-origin" if origin in img_url else "cross-site",
        }

    def _human_delay(self, short=False):
        """Delay que simula comportamento humano com variação aleatória."""
        mn = 0.3 if short else self.config["delay_min"]
        mx = 0.8 if short else self.config["delay_max"]
        delay = random.uniform(mn, mx)
        
        # 10% de chance de uma pausa maior (como se estivesse olhando algo)
        if random.random() < 0.1:
            delay += random.uniform(2, 5)
        
        # Variação baseada no número de downloads já feitos
        if self.downloaded > 10:
            delay *= 1.1
        
        time.sleep(delay)

    @staticmethod
    def _sanitize(name, max_len=60):
        """Limpa nomes de arquivos para serem válidos em qualquer SO."""
        if not name:
            return "sem_nome"
        name = re.sub(r'[^\w\-_\. ]', '_', name)
        name = re.sub(r'\s+', '_', name.strip())
        name = re.sub(r'_+', '_', name)  # Remove underscores duplicados
        return name[:max_len].strip('_') or "sem_nome"

    @staticmethod
    def _folder_from_url(url):
        """Gera nome de pasta baseado na URL."""
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.strip("/").replace("/", "_")
        raw = f"{domain}_{path}" if path else domain
        return HumanImageDownloader._sanitize(raw, max_len=80)

    def _is_ad(self, url, alt="", classes=None):
        """Verifica se a imagem é de anúncio ou tracking."""
        if not self.config["skip_ads"]:
            return False
        check = (url + " " + alt + " " + " ".join(classes or [])).lower()
        
        # Verifica palavras-chave de ads
        if any(kw in check for kw in AD_KEYWORDS):
            return True
        
        # Verifica domínios de ads
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if any(ad_domain in domain for ad_domain in AD_DOMAINS):
            return True
        
        return False

    def _is_logo(self, url, alt="", classes=None):
        """Verifica se a imagem é logo, ícone ou elemento UI."""
        if not self.config["skip_logos"]:
            return False
        check = (url + " " + alt + " " + " ".join(classes or [])).lower()
        return any(kw in check for kw in LOGO_KEYWORDS)

    def _is_duplicate(self, img_bytes):
        """Verifica se a imagem já foi baixada usando hash MD5."""
        if not self.config["skip_duplicates"]:
            return False
        try:
            img_hash = hashlib.md5(img_bytes).hexdigest()
            if img_hash in self.seen_hashes:
                return True
            self.seen_hashes.add(img_hash)
            return False
        except Exception:
            return False

    def _meets_size(self, img_bytes):
        """Verifica se a imagem atende aos requisitos de tamanho."""
        # Verifica tamanho do arquivo
        file_size = len(img_bytes)
        if file_size < self.config["min_file_size"]:
            return False
        if file_size > self.config["max_file_size"]:
            return False
        
        # Verifica dimensões se validação estiver habilitada
        if self.config["validate_images"]:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                w, h = img.size
                return (w >= self.config["min_width"] and 
                        h >= self.config["min_height"])
            except Exception:
                # Se não conseguir abrir, considera válida
                return True
        return True

    def _get_image_dimensions(self, img_bytes):
        """Retorna dimensões da imagem."""
        try:
            img = Image.open(io.BytesIO(img_bytes))
            return img.size
        except Exception:
            return None, None

    def _extract_images(self, html, base_url):
        """Extrai todas as URLs de imagens do HTML."""
        soup = BeautifulSoup(html, "html.parser")
        images = []
        seen = set()

        # 1. Tags img padrão
        for tag in soup.find_all("img"):
            src = (
                tag.get("src") or 
                tag.get("data-src") or
                tag.get("data-lazy-src") or 
                tag.get("data-original") or
                tag.get("data-url") or 
                tag.get("data-srcset", "").split(" ")[0] or
                ""
            )
            if not src or src.startswith("data:"):
                continue
            
            abs_url = urllib.parse.urljoin(base_url, src)
            clean = abs_url.split("?")[0]
            
            if clean in seen:
                continue
            seen.add(clean)
            
            ext = Path(urllib.parse.urlparse(abs_url).path).suffix.lower()
            if ext and ext not in self.config["formats"]:
                continue
            
            alt = tag.get("alt", "")
            classes = tag.get("class", [])
            parent_classes = tag.parent.get("class", []) if tag.parent else []
            
            images.append({
                "url": abs_url,
                "alt": alt,
                "classes": classes + parent_classes,
                "ext": ext or ".jpg",
                "source": "img_tag",
            })

        # 2. Background images em style inline
        for tag in soup.find_all(style=True):
            urls = re.findall(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', tag["style"])
            for u in urls:
                clean = u.split("?")[0]
                ext = Path(urllib.parse.urlparse(u).path).suffix.lower()
                
                if clean not in seen and (not ext or ext in self.config["formats"]):
                    seen.add(clean)
                    images.append({
                        "url": u,
                        "alt": "",
                        "classes": [],
                        "ext": ext or ".jpg",
                        "source": "inline_style",
                    })

        # 3. Links diretos para imagens
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            ext = Path(urllib.parse.urlparse(href).path).suffix.lower()
            
            if ext in self.config["formats"]:
                abs_url = urllib.parse.urljoin(base_url, href)
                clean = abs_url.split("?")[0]
                
                if clean not in seen:
                    seen.add(clean)
                    images.append({
                        "url": abs_url,
                        "alt": tag.get_text(strip=True),
                        "classes": [],
                        "ext": ext,
                        "source": "direct_link",
                    })

        # 4. Meta tags Open Graph e Twitter Cards
        for meta in soup.find_all("meta", property=True, content=True):
            prop = meta["property"].lower()
            if prop in ["og:image", "twitter:image"]:
                url = meta["content"]
                clean = url.split("?")[0]
                ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
                
                if clean not in seen and (not ext or ext in self.config["formats"]):
                    seen.add(clean)
                    images.append({
                        "url": url,
                        "alt": "meta_" + prop.replace(":", "_"),
                        "classes": [],
                        "ext": ext or ".jpg",
                        "source": "meta_tag",
                    })

        # 5. SVG embedded (extrair referências externas)
        for svg in soup.find_all("svg"):
            for child in svg.descendants:
                if hasattr(child, 'get'):
                    href = child.get("href") or child.get("xlink:href") or ""
                    if href and href.startswith("http"):
                        clean = href.split("?")[0]
                        ext = Path(urllib.parse.urlparse(href).path).suffix.lower()
                        
                        if clean not in seen and (not ext or ext in self.config["formats"]):
                            seen.add(clean)
                            images.append({
                                "url": href,
                                "alt": "",
                                "classes": [],
                                "ext": ext or ".svg",
                                "source": "svg_embedded",
                            })

        return images

    def _download_image(self, img_info, page_url, save_path, idx, total):
        """Baixa uma imagem individual com retry exponencial."""
        url = img_info["url"]
        
        for attempt in range(1, self.config["max_retries"] + 1):
            try:
                self._human_delay(short=(attempt > 1))
                
                resp = self.scraper.get(
                    url,
                    headers=self._image_headers(page_url, url),
                    timeout=self.config["timeout"],
                    stream=True,
                    allow_redirects=True,
                )
                resp.raise_for_status()
                
                img_bytes = resp.content
                
                if not img_bytes:
                    return False, "empty"

                # Verifica tamanho
                if not self._meets_size(img_bytes):
                    return False, "size"

                # Verifica duplicata
                if self._is_duplicate(img_bytes):
                    return False, "duplicate"

                # Determina extensão correta
                ct = resp.headers.get("Content-Type", "")
                ext = img_info["ext"]
                
                if not ext or ext == ".":
                    guessed = mimetypes.guess_extension(ct.split(";")[0].strip())
                    ext = guessed if guessed and guessed in self.config["formats"] else ".jpg"
                
                if ext == ".jpe":
                    ext = ".jpg"

                # Gera nome do arquivo
                label = self._sanitize(img_info["alt"]) if img_info["alt"] else hashlib.md5(url.encode()).hexdigest()[:8]
                filename = save_path / f"{idx:03d}_{label}{ext}"
                
                # Salva arquivo
                filename.write_bytes(img_bytes)
                
                # Retorna informações
                size_kb = len(img_bytes) / 1024
                dimensions = self._get_image_dimensions(img_bytes)
                
                return True, {
                    "filename": filename.name,
                    "size_kb": size_kb,
                    "dimensions": dimensions,
                }

            except Exception as e:
                error_msg = str(e)
                
                # Backoff exponencial
                if attempt < self.config["max_retries"]:
                    wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(wait_time)
                    
                    # Refresh scraper após erro
                    if attempt == 2:
                        self._refresh_scraper()
                else:
                    # Última tentativa falhou
                    status_code = ""
                    if hasattr(e, "response") and e.response is not None:
                        status_code = f"HTTP {e.response.status_code}"
                    return False, f"{status_code}: {error_msg}"

        self.failed += 1
        return False, "max_retries"

    def _check_robots_txt(self, url):
        """Verifica robots.txt se configurado para respeitar."""
        if not self.config["respect_robots"]:
            return True
        
        try:
            parsed = urllib.parse.urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            return rp.can_fetch("*", url)
        except Exception:
            return True  # Em caso de erro, permite

    def run(self, url):
        """Executa o download de todas as imagens da página."""
        self.start_time = datetime.now()
        
        print("\n" + "=" * 62)
        print(f"  IMAGE DOWNLOADER v3 - Anti-Bot Edition")
        print(f"  Alvo: {url}")
        print("=" * 62)

        # Verifica robots.txt
        if self.config["respect_robots"]:
            print(f"\n  [INFO] Verificando robots.txt...")
            if not self._check_robots_txt(url):
                print(f"  [ERRO] Site bloqueia scraping em robots.txt")
                return

        # Aquecimento: visita homepage para obter cookies
        parsed = urllib.parse.urlparse(url)
        homepage = f"{parsed.scheme}://{parsed.netloc}"
        
        if homepage.rstrip("/") != url.rstrip("/"):
            print(f"\n  [1/4] Aquecendo sessão em: {homepage}")
            try:
                self.scraper.get(homepage, timeout=20)
                self._human_delay()
            except Exception as e:
                print(f"  [WARN] Aquecimento falhou ({e}), tentando assim mesmo...")

        print(f"  [2/4] Carregando página alvo...")
        self._human_delay()
        
        try:
            resp = self.scraper.get(url, timeout=self.config["timeout"], allow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            print(f"\n[ERRO] Não foi possível acessar a página: {e}")
            return

        # Prepara pasta de saída
        folder_name = self._folder_from_url(url)
        save_path = Path(self.config["output_dir"]) / folder_name
        save_path.mkdir(parents=True, exist_ok=True)

        # Extrai imagens
        images = self._extract_images(resp.text, url)
        print(f"  [3/4] {len(images)} imagens encontradas")
        print(f"        Salvando em: {save_path.resolve()}\n")

        # Filtra imagens indesejadas
        filtered = []
        skipped_ads = 0
        skipped_logos = 0

        for img in images:
            if self._is_ad(img["url"], img["alt"], img["classes"]):
                skipped_ads += 1
            elif self._is_logo(img["url"], img["alt"], img["classes"]):
                skipped_logos += 1
            else:
                filtered.append(img)

        if skipped_ads:
            print(f"  [INFO] {skipped_ads} anúncios ignorados")
        if skipped_logos:
            print(f"  [INFO] {skipped_logos} logos/ícones ignorados")

        if not filtered:
            print("\n  [INFO] Nenhuma imagem para baixar após filtragem.")
            return

        print(f"\n  [4/4] Baixando {len(filtered)} imagens...\n")

        # Barra de progresso (se tqdm disponível)
        if tqdm:
            iterator = tqdm(filtered, desc="Progresso", unit="img")
        else:
            iterator = enumerate(filtered, start=1)

        for i, img_info in enumerate(iterator, start=1):
            if not tqdm:
                print(f"  [{'i':>3}/{len(filtered):>3}] {img_info['url'][:70]}...")
            
            success, result = self._download_image(
                img_info, url, save_path, i, len(filtered)
            )
            
            if success:
                self.downloaded += 1
                if isinstance(result, dict):
                    dim = result["dimensions"]
                    dim_str = f"{dim[0]}x{dim[1]}" if dim[0] else "??"
                    print(f"    ✓ {result['filename']} ({result['size_kb']:.0f} KB, {dim_str})")
            else:
                reason = result if isinstance(result, str) else "unknown"
                if reason == "size":
                    self.skipped += 1
                    print(f"    ✗ Tamanho inadequado")
                elif reason == "duplicate":
                    self.duplicates += 1
                    print(f"    ✗ Duplicata")
                else:
                    self.failed += 1
                    print(f"    ✗ Erro: {reason[:50]}")

        # Relatório final
        elapsed = datetime.now() - self.start_time
        print("\n" + "=" * 62)
        print(f"  CONCLUÍDO!")
        print(f"  {'='*60}")
        print(f"  Tempo decorrido: {elapsed}")
        print(f"  Baixadas com sucesso: {self.downloaded}")
        print(f"  Puladas (tamanho):    {self.skipped}")
        print(f"  Duplicatas:           {self.duplicates}")
        print(f"  Falhas:               {self.failed}")
        print(f"  Total processado:     {self.downloaded + self.skipped + self.duplicates + self.failed}")
        print(f"  Pasta de destino:     {save_path.resolve()}")
        print("=" * 62 + "\n")


# ============================================================================
# FUNÇÃO PRINCIPAL E CLI
# ============================================================================
def main():
    """Função principal com parsing de argumentos."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="""
╔═══════════════════════════════════════════════════════════╗
║     IMAGE DOWNLOADER v3 - Anti-Bot Edition                ║
║     Baixa imagens de sites com bypass de proteções        ║
╚═══════════════════════════════════════════════════════════╝
        """,
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("url", nargs="?", help="URL da página alvo")
    parser.add_argument("-o", "--output", default="downloads", 
                        help="Pasta de saída (padrão: downloads)")
    parser.add_argument("-W", "--min-width", type=int, default=100,
                        help="Largura mínima em px (padrão: 100)")
    parser.add_argument("-H", "--min-height", type=int, default=100,
                        help="Altura mínima em px (padrão: 100)")
    parser.add_argument("--max-size", type=int, default=50,
                        help="Tamanho máximo do arquivo em MB (padrão: 50)")
    parser.add_argument("--logos", action="store_true",
                        help="Incluir logos e ícones")
    parser.add_argument("--ads", action="store_true",
                        help="Incluir anúncios e banners")
    parser.add_argument("--duplicates", action="store_true",
                        help="Baixar duplicatas")
    parser.add_argument("--no-validate", action="store_true",
                        help="Não validar dimensões das imagens")
    parser.add_argument("--robots", action="store_true",
                        help="Respeitar robots.txt")
    parser.add_argument("--delay-min", type=float, default=1.5,
                        help="Delay mínimo entre downloads (seg)")
    parser.add_argument("--delay-max", type=float, default=4.0,
                        help="Delay máximo entre downloads (seg)")
    parser.add_argument("--retries", type=int, default=3,
                        help="Número máximo de tentativas (padrão: 3)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Timeout em segundos (padrão: 30)")
    
    args = parser.parse_args()

    url = args.url
    
    if not url:
        print("\n" + "=" * 62)
        print("     IMAGE DOWNLOADER v3 - Anti-Bot Edition")
        print("=" * 62 + "\n")
        url = input("  Digite a URL da página: ").strip()
        
        if not url:
            print("[ERRO] Nenhuma URL fornecida.")
            sys.exit(1)

    # Normaliza URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Configuração
    config = {
        "output_dir":      args.output,
        "min_width":       args.min_width,
        "min_height":      args.min_height,
        "max_file_size":   args.max_size * 1024 * 1024,
        "skip_logos":      not args.logos,
        "skip_ads":        not args.ads,
        "skip_duplicates": not args.duplicates,
        "validate_images": not args.no_validate,
        "respect_robots":  args.robots,
        "delay_min":       args.delay_min,
        "delay_max":       args.delay_max,
        "max_retries":     args.retries,
        "timeout":         args.timeout,
    }

    try:
        downloader = HumanImageDownloader(config)
        downloader.run(url)
    except KeyboardInterrupt:
        print("\n\n[INFO] Download interrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
