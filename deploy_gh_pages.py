"""
deploy_gh_pages.py  -  the "commit + push" step, done for you.

Copies index.html + thailand/ (all dataset sub-folders: corn_crop12, corn_crop3, ...) from the Python output folder into a temporary
folder, makes ONE fresh commit and force-pushes it to the `gh-pages` branch.
The branch `main` is never touched, and gh-pages history is replaced every run, so the repo does not grow.

Run alone:            python deploy_gh_pages.py            (asks for "yes")
                      python deploy_gh_pages.py --yes      (no question)
Call from your script: import deploy_gh_pages; deploy_gh_pages.run(ask=False)
"""
import datetime
import glob
import os
import shutil
import stat
import subprocess
import sys
import tempfile

SOURCE = r"D:\GIT_HUB\ndvi_dashboard_TH"          # folder your readcsv script writes the country folders into
REPO   = "https://github.com/gisfitt/ndvi_dashboard_TH.git"
HTML   = "index.html"                                     # "" = newest NDVI_05_WEB_RECHECK_V*.html (in SOURCE, then next to this file)
COUNTRIES = ["thailand"]


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True)


def _rm_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _find_html():
    if HTML:
        p = os.path.join(SOURCE, HTML)
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        return p
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    for folder in (SOURCE, here):
        cands += glob.glob(os.path.join(folder, "NDVI_05_WEB_RECHECK_V*.html"))
    if not cands:
        raise FileNotFoundError(f"No NDVI_05_WEB_RECHECK_V*.html in {SOURCE} or next to this file")
    return max(cands, key=os.path.getmtime)


def _check_data():
    """Each country holds dataset sub-folders (thailand/corn_crop12/ ...), each with est_ndvi.json + raw_index.json (or raw_ndvi.json)."""
    for c in COUNTRIES:
        base = os.path.join(SOURCE, c)
        subs = [d for d in sorted(os.listdir(base)) if os.path.isdir(os.path.join(base, d))] if os.path.isdir(base) else []
        if not subs:
            raise FileNotFoundError(f"No dataset folders in {base} - run the data script first")
        for d in subs:
            p = os.path.join(base, d)
            if not os.path.exists(os.path.join(p, "est_ndvi.json")):
                raise FileNotFoundError(f"Missing {c}/{d}/est_ndvi.json")
            if not (os.path.exists(os.path.join(p, "raw_index.json")) or os.path.exists(os.path.join(p, "raw_ndvi.json"))):
                raise FileNotFoundError(f"Missing {c}/{d}/raw_index.json (or raw_ndvi.json)")
            print(f"  dataset OK: {c}/{d}")
    for dp, _, fs in os.walk(SOURCE):
        if ".git" in dp.split(os.sep):
            continue
        for f in fs:
            mb = os.path.getsize(os.path.join(dp, f)) / 1048576
            if mb > 100:
                raise RuntimeError(f"{os.path.join(dp, f)} is {mb:.0f} MB - GitHub rejects files over 100 MB")
            if mb > 50:
                print(f"  WARNING: {f} is {mb:.0f} MB (GitHub warns over 50 MB)")


def run(ask=True):
    if shutil.which("git") is None:
        raise RuntimeError("git is not installed or not on PATH")
    _check_data()
    html = _find_html()
    print("HTML:", html)

    tmp = tempfile.mkdtemp(prefix="ndvi_deploy_")
    try:
        shutil.copy2(html, os.path.join(tmp, "index.html"))
        for c in COUNTRIES:
            shutil.copytree(os.path.join(SOURCE, c), os.path.join(tmp, c))
        open(os.path.join(tmp, ".nojekyll"), "w").close()

        _git(["init", "-q", "-b", "gh-pages"], tmp)
        _git(["config", "core.autocrlf", "false"], tmp)
        for key, val in (("user.name", "dashboard-deploy"), ("user.email", "deploy@localhost")):
            has = subprocess.run(["git", "config", key], cwd=tmp, capture_output=True, text=True).stdout.strip()
            if not has:
                _git(["config", key, val], tmp)
        _git(["add", "-A"], tmp)
        _git(["commit", "-q", "-m", "Deploy " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")], tmp)
        _git(["remote", "add", "origin", REPO], tmp)

        size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(tmp) if ".git" not in d for f in fs)
        print(f"Site size: {size / 1048576:.1f} MB (uncompressed)")
        print(f"Will FORCE-PUSH gh-pages to {REPO} (only that branch's history is replaced).")
        if ask and input("Type yes to continue: ").strip().lower() != "yes":
            print("Cancelled.")
            return False
        _git(["push", "--force", "origin", "gh-pages"], tmp)
        print("Done. GitHub Pages updates in about a minute.")
        return True
    finally:
        shutil.rmtree(tmp, onerror=_rm_readonly)


if __name__ == "__main__":
    run(ask="--yes" not in sys.argv)
