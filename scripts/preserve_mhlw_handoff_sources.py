#!/usr/bin/env python3
"""Prepare or restore a local private transfer bundle using pinned official bytes."""
import argparse
import hashlib
import shutil
from pathlib import Path
from urllib.request import urlopen

from build_mhlw_resource_handoff import AUDIT, OUT, ROOT, read, write, sha


def manifest():
    earlier=AUDIT/"final_resource_review"
    result=[]
    for row in read(earlier/"pdf_preservation_and_rights.csv"):
        name=row["filename"]
        directory="mhlw-early-2020" if row["series"]=="early" else "mhlw-weekly-definition-pdfs"
        result.append((f"{directory}/{name}",row["url"],int(row["expected_bytes"]),row["sha256"],row["decision"]))
    for name,directory,sizes in (("supplemental_source_manifest.csv","mhlw-final-downloads","bytes"),
                                  ("critical_care_acquisition.csv","mhlw-handoff-critical","size")):
        parent=earlier if directory=="mhlw-final-downloads" else OUT
        for row in read(parent/name):
            if row["status"]=="downloaded":
                name=f"{row['id']}.{row['format']}"
                result.append((f"{directory}/{name}",row["url"],int(row[sizes]),row["sha256"],"移行用・個別公開条件を確認"))
    if len({r[0] for r in result})!=len(result):
        raise ValueError("Duplicate destination")
    return result


def verify(path, size, checksum):
    if not path.is_file() or path.stat().st_size!=size or sha(path)!=checksum:
        raise ValueError(f"Missing or changed bytes: {path}")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work",type=Path,required=True)
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--restore",action="store_true",help="Fetch official bytes only for missing files")
    parser.add_argument("--verify-only",action="store_true")
    args=parser.parse_args()
    work=args.work.resolve()
    bundle=args.bundle.resolve()
    if work.is_relative_to(ROOT) or bundle.is_relative_to(ROOT):
        parser.error("Private originals belong outside the Git tree")
    files=[]
    for relative,url,size,checksum,rights in manifest():
        target=bundle/relative
        current=work/relative
        if not target.exists() and not args.verify_only:
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if current.is_file():
                verify(current,size,checksum)
                shutil.copyfile(current,target)
            elif args.restore:
                with urlopen(url,timeout=30) as response:
                    payload=response.read()
                if len(payload)!=size or hashlib.sha256(payload).hexdigest()!=checksum:
                    raise ValueError(f"Official edition changed: {url}")
                target.write_bytes(payload)
        verify(target,size,checksum)
        files.append(dict(bundle_path=relative,url=url,bytes=size,sha256=checksum,redistribution=rights))
    if not args.verify_only:
        write(OUT/"private_transfer_manifest.csv",files)
        shutil.copyfile(OUT/"private_transfer_manifest.csv",bundle/"SHA256_manifest.csv")
    print(f"Verified {len(files)} files, {sum(item['bytes'] for item in files):,} bytes")


if __name__=="__main__":
    main()
