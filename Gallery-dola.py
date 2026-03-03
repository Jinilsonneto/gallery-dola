"""
IMAGE DOWNLOADER - Anti-Bot Edition v2
Baixa imagens de qualquer site como um humano real
Suporte a Cloudflare e protecoes anti-bot via cloudscraper
"""

import re
import time
import random
import hashlib
import mimetypes
import urllib.parse
from pathlib import Path
import io

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

if missing:
    print(f"[ERRO] Dependencias faltando: {', '.join(missing)}")
    print("Execute: pip install " + " ".join(missing) + " --break-system-packages")
    exit(1)

DEFAULT_CONFIG = {
    "min_width":   100,
    "min_height":  100,
    "skip_logos":  True,
    "delay_min":   1.5,
    "delay_max":   4.0,
    "max_retries": 3,
    "output_dir":  "downloads",
    "formats": [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"],
}

LOGO_KEYWORDS = [
    "logo", "icon", "favicon", "sprite", "badge", "watermark",
    "brand", "seal", "emblem", "avatar", "thumbnail-icon",
    "site-icon", "wp-emoji", "loading", "placeholder", "blank", "spacer",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


class HumanImageDownloader:
    def __init__(self, config=None):
        self.config     = {**DEFAULT_CONFIG, **(config or {})}
        self.scraper    = self._build_scraper()
        self.downloaded = 0
        self.skipped    = 0
        self.failed     = 0

    def _build_scraper(self):
        ua = random.choice(USER_AGENTS)
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True},
            delay=random.uniform(3, 7),
        )
        scraper.headers.update({
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
        return scraper

    def _image_headers(self, page_url, img_url):
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
        mn = 0.3 if short else self.config["delay_min"]
        mx = 0.8 if short else self.config["delay_max"]
        delay = random.uniform(mn, mx)
        if random.random() < 0.1:
            delay += random.uniform(2, 5)
        time.sleep(delay)

    @staticmethod
    def _sanitize(name, max_len=60):
        name = re.sub(r'[^\w\-_\. ]', '_', name)
        name = re.sub(r'\s+', '_', name.strip())
        return name[:max_len] or "sem_nome"

    @staticmethod
    def _folder_from_url(url):
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path   = parsed.path.strip("/").replace("/", "_")
        raw    = f"{domain}_{path}" if path else domain
        return HumanImageDownloader._sanitize(raw)

    def _is_logo(self, url, alt="", classes=None):
        if not self.config["skip_logos"]:
            return False
        check = (url + " " + alt + " " + " ".join(classes or [])).lower()
        return any(kw in check for kw in LOGO_KEYWORDS)

    def _meets_size(self, img_bytes):
        try:
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            return w >= self.config["min_width"] and h >= self.config["min_height"]
        except Exception:
            return True

    def _extract_images(self, html, base_url):
        soup   = BeautifulSoup(html, "html.parser")
        images = []
        seen   = set()

        for tag in soup.find_all("img"):
            src = (
                tag.get("src") or tag.get("data-src") or
                tag.get("data-lazy-src") or tag.get("data-original") or
                tag.get("data-url") or ""
            )
            if not src or src.startswith("data:"):
                continue
            abs_url = urllib.parse.urljoin(base_url, src)
            clean   = abs_url.split("?")[0]
            if clean in seen:
                continue
            seen.add(clean)
            ext = Path(urllib.parse.urlparse(abs_url).path).suffix.lower()
            if ext and ext not in self.config["formats"]:
                continue
            alt            = tag.get("alt", "")
            classes        = tag.get("class", [])
            parent_classes = tag.parent.get("class", []) if tag.parent else []
            images.append({
                "url": abs_url, "alt": alt,
                "classes": classes + parent_classes,
                "ext": ext or ".jpg",
            })

        # Backgrounds CSS inline
        for tag in soup.find_all(style=True):
            urls = re.findall(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', tag["style"])
            for u in urls:
                clean = u.split("?")[0]
                ext   = Path(urllib.parse.urlparse(u).path).suffix.lower()
                if clean not in seen and (not ext or ext in self.config["formats"]):
                    seen.add(clean)
                    images.append({"url": u, "alt": "", "classes": [], "ext": ext or ".jpg"})

        # Links diretos para imagens
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            ext  = Path(urllib.parse.urlparse(href).path).suffix.lower()
            if ext in self.config["formats"]:
                abs_url = urllib.parse.urljoin(base_url, href)
                clean   = abs_url.split("?")[0]
                if clean not in seen:
                    seen.add(clean)
                    images.append({
                        "url": abs_url, "alt": tag.get_text(strip=True),
                        "classes": [], "ext": ext,
                    })

        return images

    def _download_image(self, img_info, page_url, save_path, idx):
        url = img_info["url"]
        for attempt in range(1, self.config["max_retries"] + 1):
            try:
                self._human_delay(short=(attempt > 1))
                resp = self.scraper.get(
                    url,
                    headers=self._image_headers(page_url, url),
                    timeout=30, stream=True, allow_redirects=True,
                )
                resp.raise_for_status()
                img_bytes = resp.content
                if not img_bytes:
                    return False

                if not self._meets_size(img_bytes):
                    print(f"  [SKIP] [{idx:03d}] Muito pequena, pulando.")
                    self.skipped += 1
                    return False

                ct  = resp.headers.get("Content-Type", "")
                ext = img_info["ext"]
                if not ext or ext == ".":
                    guessed = mimetypes.guess_extension(ct.split(";")[0].strip()) or ".jpg"
                    ext     = guessed if guessed in self.config["formats"] else ".jpg"
                if ext == ".jpe":
                    ext = ".jpg"

                label    = self._sanitize(img_info["alt"]) if img_info["alt"] else hashlib.md5(url.encode()).hexdigest()[:8]
                filename = save_path / f"{idx:03d}_{label}{ext}"
                filename.write_bytes(img_bytes)
                size_kb  = len(img_bytes) / 1024
                print(f"  [OK]   [{idx:03d}] {filename.name}  ({size_kb:.0f} KB)")
                self.downloaded += 1
                return True

            except Exception as e:
                code = ""
                if hasattr(e, "response") and e.response is not None:
                    code = f"HTTP {e.response.status_code} - "
                print(f"  [ERR]  [{idx:03d}] {code}{e} - tentativa {attempt}/{self.config['max_retries']}")
                time.sleep(attempt * 2)

        self.failed += 1
        return False

    def run(self, url):
        print("\n" + "="*62)
        print(f"  Alvo : {url}")
        print("="*62)

        # Aquecimento: visita homepage para obter cookies
        parsed   = urllib.parse.urlparse(url)
        homepage = f"{parsed.scheme}://{parsed.netloc}"
        if homepage.rstrip("/") != url.rstrip("/"):
            print(f"\n  [1/3] Aquecendo sessao em: {homepage}")
            try:
                self.scraper.get(homepage, timeout=20)
                self._human_delay()
            except Exception as e:
                print(f"  [WARN] Aquecimento falhou ({e}), tentando assim mesmo...")

        print(f"  [2/3] Carregando pagina alvo...")
        self._human_delay()
        try:
            resp = self.scraper.get(url, timeout=30, allow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            print(f"\n[ERRO] Nao foi possivel acessar a pagina: {e}")
            return

        folder_name = self._folder_from_url(url)
        save_path   = Path(self.config["output_dir"]) / folder_name
        save_path.mkdir(parents=True, exist_ok=True)

        images = self._extract_images(resp.text, url)
        print(f"  [3/3] {len(images)} imagens encontradas")
        print(f"        Salvando em: {save_path.resolve()}\n")

        filtered = []
        for img in images:
            if self._is_logo(img["url"], img["alt"], img["classes"]):
                self.skipped += 1
            else:
                filtered.append(img)

        skipped_logos = len(images) - len(filtered)
        if skipped_logos:
            print(f"  [INFO] {skipped_logos} logos/icones ignorados\n")

        if not filtered:
            print("  [INFO] Nenhuma imagem para baixar.")
            return

        print(f"  Baixando {len(filtered)} imagens...\n")

        for idx, img_info in enumerate(filtered, start=1):
            print(f"  [DL]   [{idx:03d}/{len(filtered):03d}] {img_info['url'][:75]}")
            self._download_image(img_info, url, save_path, idx)

        print("\n" + "="*62)
        print(f"  Concluido!")
        print(f"  Baixadas : {self.downloaded}")
        print(f"  Puladas  : {self.skipped}")
        print(f"  Falhas   : {self.failed}")
        print(f"  Pasta    : {save_path.resolve()}")
        print("="*62 + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Image Downloader v2 - Bypass anti-bot com cloudscraper",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("url",            nargs="?",               help="URL da pagina alvo")
    parser.add_argument("-o", "--output", default="downloads",     help="Pasta de saida (padrao: downloads)")
    parser.add_argument("-W", "--min-width",  type=int, default=100, help="Largura minima em px (padrao: 100)")
    parser.add_argument("-H", "--min-height", type=int, default=100, help="Altura minima em px (padrao: 100)")
    parser.add_argument("--logos",        action="store_true",     help="Incluir logos e icones")
    parser.add_argument("--delay-min",    type=float, default=1.5, help="Delay minimo entre downloads (seg)")
    parser.add_argument("--delay-max",    type=float, default=4.0, help="Delay maximo entre downloads (seg)")
    args = parser.parse_args()

    url = args.url
    if not url:
        print("\n" + "="*62)
        print("     IMAGE DOWNLOADER v2 - Anti-Bot Edition")
        print("="*62 + "\n")
        url = input("  Digite a URL da pagina: ").strip()
        if not url:
            print("[ERRO] Nenhuma URL fornecida.")
            return

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    config = {
        "output_dir":  args.output,
        "min_width":   args.min_width,
        "min_height":  args.min_height,
        "skip_logos":  not args.logos,
        "delay_min":   args.delay_min,
        "delay_max":   args.delay_max,
    }

    HumanImageDownloader(config).run(url)


if __name__ == "__main__":
    main()
