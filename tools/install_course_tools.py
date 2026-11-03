#!/usr/bin/env python3
"""Install a pinned official OSS CAD Suite outside git. No sudo/push/tag.

Release asset and SHA256 verified against the official GitHub release API.
Keep Ubuntu Yosys 0.33 for M1 reference reproduction. Use this suite for M2.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import urllib.request

RELEASE='2026-10-27'
ASSET='oss-cad-suite-linux-x64-20261027.tgz'
SHA256='9fa347adb4a86e45472c55ee6fb286a91243228e856ccb408ff1bf0cfeef58ae'
URL='https://github.com/YosysHQ/oss-cad-suite-build/releases/download/'+RELEASE+'/'+ASSET
ROOT=Path(__file__).resolve().parents[1]


def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def version(binary,flag):
    p=subprocess.run([str(binary),flag],capture_output=True,text=True,timeout=60)
    text=p.stdout+p.stderr
    m=re.search(r'(\d+)\.(\d+)',text)
    if not m:raise RuntimeError('Unable to read tool version: '+str(binary))
    return tuple(map(int,m.groups())),text.splitlines()[0]


def main():
    if os.uname().machine!='x86_64':raise SystemExit('This pinned bundle is for WSL/Linux x86_64.')
    base=Path.home()/'dd2-tools';base.mkdir(exist_ok=True)
    archive=base/ASSET
    if not archive.is_file() or digest(archive)!=SHA256:
        part=archive.with_suffix('.download')
        print('Downloading official OSS CAD Suite (747 MB); progress follows.',flush=True)
        req=urllib.request.Request(URL,headers={'User-Agent':'DD2-GB4-course-setup'})
        size=0;mark=0
        with urllib.request.urlopen(req,timeout=60) as response,part.open('wb') as f:
            while block:=response.read(4*1024*1024):
                f.write(block);size+=len(block)
                if size-mark>=32*1024*1024:
                    print(f'Downloaded {size//1024//1024} MiB',flush=True);mark=size
        if digest(part)!=SHA256:raise RuntimeError('Download SHA256 mismatch; no tools were installed.')
        part.replace(archive)
    print('Official release archive SHA256 verified.',flush=True)
    install=base/('oss-'+RELEASE)
    if not install.exists():
        stage=Path(tempfile.mkdtemp(prefix='dd2-tools-',dir=base))
        with tarfile.open(archive) as tar:
            if any(not m.name.startswith(('oss-cad-suite/','./oss-cad-suite/')) and m.name not in ('oss-cad-suite','./oss-cad-suite') for m in tar.getmembers()):
                raise RuntimeError('Unexpected archive layout; left unchanged.')
            tar.extractall(stage,filter='data')
        (stage/'oss-cad-suite').rename(install);stage.rmdir()
    bindir=install/'bin'
    yv,ys=version(bindir/'yosys','-V');iv,ivs=version(bindir/'iverilog','-V')
    if yv<(0,34) or iv<(13,0):raise RuntimeError('Pinned bundle does not meet course minimum versions.')
    if not (bindir/'yosys-abc').is_file():raise RuntimeError('Bundled yosys-abc missing.')
    # A make include keeps the selected tools consistent in every new shell.
    if any(c in str(bindir) for c in ' #$\n'):
        raise RuntimeError('Install path is unsupported by the make include.')
    config=ROOT/'config';config.mkdir(exist_ok=True)
    (config/'tools.mk').write_text('export PATH := '+str(bindir)+':$(HOME)/.local/bin:$(PATH)\n'
        'export DD2_YOSYS := '+str(bindir/'yosys')+'\n'
        'export DD2_ABC := '+str(bindir/'yosys-abc')+'\n')
    record={'release':RELEASE,'source':URL,'archive_sha256':SHA256,
            'yosys':ys,'iverilog':ivs,'reference_yosys':'/usr/bin/yosys',
            'note':'Host-specific paths stay in ignored config/tools.mk. M1 uses Ubuntu reference tools; M2 uses this pinned suite.'}
    (config/'tools-install.json').write_text(json.dumps(record,indent=2)+'\n')
    print(ys);print(ivs)
    print('Installed and selected for make. Next: make check-versions, make test, make all.',flush=True)


if __name__=='__main__':main()
