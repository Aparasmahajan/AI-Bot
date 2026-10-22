"""Today's commits from git (design §9.6, JNL-1): SHA, repository, branch, time, message, files and lines added and
removed, from `git log` in every repository under the scan roots, plus uncommitted changes. Only commits by your
own git email are counted. git is run without a window and nothing is changed in any repository."""
import datetime, logging, os, re, shutil, subprocess
from pathlib import Path

log = logging.getLogger('mwb.git')
SKIP = {'node_modules', '.venv', 'venv', '__pycache__', '.git', 'dist', 'build', 'target', '.idea', '.vs', 'bin',
        'obj', '.gradle', '.next', 'site-packages'}
NO_WINDOW = 0x08000000


def _git(args, cwd=None, timeout=20):
    exe = shutil.which('git')
    if not exe:
        return None
    try:
        p = subprocess.run([exe, *args], cwd=cwd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW,
                           encoding='utf-8', errors='replace')
    except (OSError, subprocess.TimeoutExpired) as e:
        log.info('git failed: %s', type(e).__name__)
        return None
    return p.stdout if p.returncode == 0 else None


def author(setting='auto'):
    """Your git email: the setting, or `git config --global user.email`."""
    if setting and setting != 'auto':
        return setting
    out = _git(['config', '--global', 'user.email'])
    return out.strip() if out else ''


def find_repos(roots, max_depth=4):
    """Folders holding a .git, under each root; a repository's own subfolders are not searched further."""
    found = []
    for root in roots:
        root = Path(os.path.expandvars(root))
        if not root.is_dir():
            continue
        stack = [(root, 0)]
        while stack:
            folder, depth = stack.pop()
            if (folder / '.git').exists():
                found.append(folder)
                continue
            if depth >= max_depth:
                continue
            try:
                subs = [p for p in folder.iterdir() if p.is_dir() and p.name not in SKIP and not p.name.startswith('$')]
            except OSError:
                continue
            stack += [(p, depth + 1) for p in subs]
    return sorted(set(found), key=lambda p: p.name.lower())


def _branch(source):
    for prefix in ('refs/heads/', 'refs/remotes/', 'refs/tags/'):
        if source.startswith(prefix):
            return source[len(prefix):]
    return source


def commits(repo, start, end, email):
    """[{'sha', 'short', 'time', 'repo', 'branch', 'message', 'files', 'added', 'removed'}] between start and end
    (datetimes, by commit time), by this author, on any branch. Merges count once with no lines."""
    if not email:
        return []
    out = _git(['-C', str(repo), 'log', '--all', '--source', f'--since={start:%Y-%m-%d %H:%M:%S}',
                f'--until={end:%Y-%m-%d %H:%M:%S}', f'--author={email}', '--date=iso-strict',
                '--format=%x1e%H%x1f%h%x1f%cd%x1f%S%x1f%s', '--shortstat'])
    if not out:
        return []
    rows, seen = [], set()
    for chunk in out.split('\x1e')[1:]:
        head, _, rest = chunk.partition('\n')
        parts = head.split('\x1f')
        if len(parts) < 5 or parts[0] in seen:
            continue
        seen.add(parts[0])
        stat = {k: int(v) for v, k in re.findall(r'(\d+) (file|insertion|deletion)', rest)}
        when = datetime.datetime.fromisoformat(parts[2]).astimezone().replace(tzinfo=None)
        rows.append({'sha': parts[0], 'short': parts[1][:7], 'time': when, 'repo': Path(repo).name,
                     'branch': _branch(parts[3]), 'message': parts[4].strip()[:200], 'files': stat.get('file', 0),
                     'added': stat.get('insertion', 0), 'removed': stat.get('deletion', 0)})
    return rows


def uncommitted(repo):
    """How many files have changes not yet committed, or None if git couldn't say."""
    out = _git(['-C', str(repo), 'status', '--porcelain'])
    return None if out is None else len([line for line in out.splitlines() if line.strip()])


def day(roots, start, end, email):
    """(commits for all repositories, newest first; {repo name: uncommitted files} for repos with commits).
    Four repositories at a time: git spends most of its time waiting on the disk."""
    from concurrent.futures import ThreadPoolExecutor

    def one(repo):
        rows = commits(repo, start, end, email)
        return rows, (uncommitted(repo) if rows else None)
    all_rows, dirty = [], {}
    repos = find_repos(roots)
    with ThreadPoolExecutor(4) as pool:
        for repo, (rows, n) in zip(repos, pool.map(one, repos)):
            all_rows += rows
            if n:
                dirty[repo.name] = n
    all_rows.sort(key=lambda r: r['time'], reverse=True)
    return all_rows, dirty
