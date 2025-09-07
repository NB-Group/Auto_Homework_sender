import os
import sys
import argparse
import tempfile
import time
import shutil
import subprocess
from typing import Optional, List, Tuple

try:
    import requests
except Exception as e:
    print("[Init] Missing requests, please install: pip install requests")
    raise

OWNER_REPO_DEFAULT = 'NB-Group/Auto_Homework_sender'


def gh_get_json(url: str) -> Tuple[int, dict]:
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    token = os.environ.get('AH_GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = requests.get(url, headers=headers, timeout=12)
    try:
        print('[HTTP]', url, '->', r.status_code)
    except Exception:
        pass
    return r.status_code, r.json()


def find_asset_url(owner_repo: str, prefer: str = 'zip') -> Tuple[str, str]:
    """Return (latest_tag, asset_url) preferring zip then exe if prefer='auto' or 'zip'."""
    status, info = gh_get_json(f'https://api.github.com/repos/{owner_repo}/releases/latest')
    latest_tag = (info or {}).get('tag_name') or ''
    assets = (info or {}).get('assets') or []

    def pick(assets, ext):
        for a in assets:
            name = (a.get('name') or '').lower()
            if name.endswith(ext):
                return a.get('browser_download_url')
        return ''

    order: List[str]
    if prefer == 'exe':
        order = ['.exe', '.zip']
    elif prefer == 'zip':
        order = ['.zip', '.exe']
    else:  # auto
        order = ['.zip', '.exe']

    asset_url = ''
    for ext in order:
        asset_url = pick(assets, ext)
        if asset_url:
            break

    if not asset_url:
        status, rels = gh_get_json(f'https://api.github.com/repos/{owner_repo}/releases?per_page=5')
        if isinstance(rels, list):
            for rel in rels:
                if rel.get('draft') or rel.get('prerelease'):
                    continue
                latest_tag = rel.get('tag_name') or latest_tag
                assets2 = rel.get('assets') or []
                for ext in order:
                    asset_url = pick(assets2, ext)
                    if asset_url:
                        break
                if asset_url:
                    break

    return latest_tag, asset_url


def build_candidates(asset_url: str) -> List[str]:
    candidates = []
    if asset_url and asset_url.startswith('https://'):
        base = asset_url
        candidates.extend([
            'https://hk.gh-proxy.com/' + base,
            'https://gh-proxy.com/' + base,
            'https://cdn.gh-proxy.com/' + base,
            'https://edgeone.gh-proxy.com/' + base,
            'https://ghproxy.com/' + base,
            'https://mirror.ghproxy.com/' + base,
            base,
        ])
    # 去重
    seen = set()
    dedup = []
    for u in candidates:
        if u and u not in seen:
            dedup.append(u)
            seen.add(u)
    return dedup


def download_to_temp(urls: List[str], suffix: str) -> str:
    tmp_dir = tempfile.gettempdir()
    path = os.path.join(tmp_dir, f'AutoHomework_Update_{int(time.time())}{suffix}')
    last_err = None
    for url in urls:
        print('[DL] try:', url)
        try:
            with requests.get(url, stream=True, timeout=45, allow_redirects=True, proxies={}) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get('Content-Length') or 0)
                received = 0
                with open(path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024*256):
                        if chunk:
                            f.write(chunk)
                            received += len(chunk)
                            if total:
                                pct = int(received * 100 / total)
                                print(f'\r[DL] {pct}% ({received}/{total})', end='')
                print('\n[DL] saved ->', path)
            return path
        except Exception as e:
            print('[DL] failed:', e)
            last_err = e
    raise RuntimeError(f'Download failed: {last_err}')


def copy_merge(src: str, dst: str, dry_run: bool = False):
    print('[CP] src:', src)
    print('[CP] dst:', dst)
    if not os.path.exists(dst):
        if not dry_run:
            os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out_dir = dst if rel == '.' else os.path.join(dst, rel)
        if not dry_run:
            os.makedirs(out_dir, exist_ok=True)
        for d in dirs:
            if not dry_run:
                os.makedirs(os.path.join(out_dir, d), exist_ok=True)
        for fn in files:
            s = os.path.join(root, fn)
            t = os.path.join(out_dir, fn)
            print('[CP] ->', t)
            if not dry_run:
                shutil.copy2(s, t)


def extract_and_copy(zip_path: str, target: str, dry_run: bool = False) -> str:
    import zipfile
    work = os.path.join(tempfile.gettempdir(), f'ah_unzip_{int(time.time())}')
    if not dry_run:
        os.makedirs(work, exist_ok=True)
    print('[ZIP] extracting to', work)
    if not dry_run:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(work)
    # detect single root directory
    root_entries = [p for p in (os.listdir(work) if not dry_run else [])]
    src = work
    if not dry_run and len(root_entries) == 1 and os.path.isdir(os.path.join(work, root_entries[0])):
        src = os.path.join(work, root_entries[0])
    copy_merge(src, target, dry_run=dry_run)
    return work


def find_executable(target: str) -> Optional[str]:
    for name in ('AutoHomework.exe', 'main.exe'):
        p = os.path.join(target, name)
        if os.path.exists(p):
            return p
    # recurse
    for root, _, files in os.walk(target):
        for name in ('AutoHomework.exe', 'main.exe'):
            if name in files:
                return os.path.join(root, name)
    return None


def main():
    ap = argparse.ArgumentParser(description='Standalone updater for Auto Homework')
    ap.add_argument('--owner', default=OWNER_REPO_DEFAULT, help='owner/repo')
    ap.add_argument('--target', default='', help='target directory to overwrite (default: exe dir or this script dir)')
    ap.add_argument('--prefer', default='zip', choices=['zip', 'exe', 'auto'])
    ap.add_argument('--start', action='store_true', help='start app after install')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--url', default='', help='override asset url')
    args = ap.parse_args()

    # resolve target dir
    if args.target:
        target_dir = os.path.abspath(os.path.expandvars(args.target))
    else:
        exe_base = os.path.basename(sys.executable).lower()
        if exe_base.endswith('.exe') and exe_base not in ('python.exe', 'pythonw.exe'):
            target_dir = os.path.dirname(sys.executable)
        else:
            target_dir = os.path.abspath(os.path.dirname(__file__))
    print('[Target]', target_dir)

    # resolve asset
    if args.url:
        asset_url = args.url
        tag = 'manual'
    else:
        tag, asset_url = find_asset_url(args.owner, prefer=args.prefer)
    if not asset_url:
        print('[Error] No asset found')
        sys.exit(2)
    print('[Latest]', tag)
    print('[Asset]', asset_url)

    urls = build_candidates(asset_url)
    suffix = '.zip' if asset_url.lower().endswith('.zip') else '.exe'
    path = download_to_temp(urls, suffix)

    if suffix == '.zip':
        work = extract_and_copy(path, target_dir, dry_run=args.dry_run)
        if not args.dry_run:
            try:
                os.remove(path)
            except Exception:
                pass
            try:
                shutil.rmtree(work, ignore_errors=True)
            except Exception:
                pass
        exe = find_executable(target_dir)
        print('[Start candidate]', exe)
        if args.start and exe and not args.dry_run:
            print('[Start] launching', exe)
            try:
                subprocess.Popen([exe], close_fds=True)
            except Exception as e:
                print('[Start] failed:', e)
    else:
        print('[EXE] installer downloaded ->', path)
        if not args.dry_run:
            try:
                subprocess.Popen([path, '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS'], close_fds=True)
            except Exception as e:
                print('[EXE] start failed:', e)

    print('[Done]')


if __name__ == '__main__':
    main()
