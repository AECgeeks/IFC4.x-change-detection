import os
import re
import sys
import glob
import shutil
import itertools
import subprocess

from collections import defaultdict

# pip install pyyaml
import yaml
# pip install unidiff==0.7.0
import unidiff

def run(*args, can_fail=False, decode='ascii', capture_output=True, **kwargs):
    print(*args)
    proc = subprocess.run([*args], capture_output=capture_output, **kwargs)
    # print(proc.stdout.decode('ascii'))
    # print(proc.stderr.decode('ascii'))
    if not can_fail:
        if proc.returncode != 0:
            if capture_output:
                print(proc.stderr.decode('ascii', errors="ignore"))
            # sys.exit(1)
            return False
        
    output = proc.stdout
    if decode:
        output = output.decode(decode, errors="ignore")
        
    return output


def git(*args, **kwargs):
    return run("git", "-C", "repo", *args, **kwargs)

git("reset", "--hard")
git("checkout", "master")
git("pull", can_fail=True)

if "--topics" in sys.argv[1:]:
    #                                             v-- skip first, is the basis
    #                                                v-- skip last, is the artefact
    shas = set(sum(([p[0:7] for p in l.split("_")[1:-1]] for l in os.listdir("diffs")), []))
    lines = git("log", '--pretty=format:%h  %ad  %<(16)%an %s', "--date=short").split("\n")
    for l in lines:
        if l[0:7] in shas:
            print(l.strip())
    exit(0)

shas = git("log", "--format=format:%H").split("\n")

try:
    first_storage = [os.path.exists(f"storage/{sha}") for sha in shas].index(True)
except:
    first_storage = 100000

for sha in ([] if "--no-build" in sys.argv else shas[0:first_storage]):
    print(sha)
    git("reset", "--hard")
    git("checkout", sha, can_fail=True)
    git("clean", "-fdX")
    
    code = open("repo/code/xmi_document.py").read()
    code = re.sub(r'SCHEMA_NAME = .+', 'SCHEMA_NAME = "IFC4X3_DEV"', code)
    code = re.sub(r'SCHEMA_NAME \+= .+', 'pass', code)
    open("repo/code/xmi_document.py", "w").write(code)
    
    open("repo/code/sanity_checker.py", "w").write("")
    
    code = open("repo/code/express_diff/express_parser.py").read()
    code = code.replace('"rb"', '"r"')
    code = code.replace("m = pickle.load(f)", "import io; m = pickle.load(io.BytesIO(f.read().encode('ascii')))")
    open("repo/code/express_diff/express_parser.py", "w").write(code)
    
    open("repo/code/express_diff/__main__.py", "w").write("print('skipped')")
    
    code = open("repo/code/to_pset.py").read()
    code = code.replace('--compare', '--ignored')
    open("repo/code/to_pset.py", "w").write(code)
    
    code = open("repo/code/main.py").read()
    code = code.replace('print("Running:", script)', 'if script in ("to_po", "to_bsdd"): continue')
    open("repo/code/main.py", "w").write(code)
    
    if run(sys.executable, "repo/code/main.py") is False:
        print(sha, "failed")
        continue

#     deprecated_entities = run(sys.executable, cwd="repo/code", input=b"""
# import xmi_document
# 
# xmi_doc = xmi_document.xmi_document('../schemas/IFC.xml')
# for item in xmi_doc:
#     if item.type == "ENTITY":    
#         if xmi_doc.xmi.tags["deprecated"].get(item.id, False):
#             print(item.name)
# """)
# 
#     with open("repo/output/deprecated_entities.txt", "w") as f:
#         for x in sorted(x for x in deprecated_entities.split("\n") if x):
#             print(x, file=f)
    
    shutil.move("repo/output", f"storage/{sha}")
    
LABELS = "schema", "properties"
ARTEFACTS = "IFC.exp", "psd"

def get_commit_artefacts(shas, artefacts=ARTEFACTS):
    return [f"{sha}/{artefact}" for sha, artefact in itertools.product(shas, artefacts)]

for new_sha in ([] if "--no-diff" in sys.argv else shas):

    commit_artefacts = get_commit_artefacts([new_sha])
    if not all(os.path.exists("storage/"+p) for p in commit_artefacts):
        print(f"{new_sha} failed, skipping")
        continue
            
    is_merge_commit = False
    is_root = False
    
    sha = new_sha
    
    sha_list = [sha]
    
    while True:
        old_shas = git("log", "--pretty=%P", "-1", sha).strip().split(" ")
        is_merge_commit = len(old_shas) != 1
        is_root = len(old_shas) == 0
        if is_merge_commit or is_root:
            print(f"{sha} is {'a merge commit' if is_merge_commit else 'the root'}")
            break
            
        commit_artefacts = get_commit_artefacts([old_shas[0]])
            
        if all(os.path.exists("storage/"+p) for p in commit_artefacts):
            sha_list.append(old_shas[0])
            break
        else:
            print(f"{old_shas[0]} failed, proceeding to ancestor")
            sha = old_shas[0]
            sha_list.append(sha)
    
    if is_merge_commit:
        continue
        
    if is_root:
        break
    
    old_new_sha = [old_shas[0], new_sha]
        
    print(*old_new_sha)
    
    for label, artefact in zip(LABELS, ARTEFACTS):
    
        output = run(
            r"C:\Program Files\Git\usr\bin\diff.exe",
            "-N",
            "-U2",
            *get_commit_artefacts(old_new_sha, [artefact]),
            can_fail=True,
            decode=None,
            cwd="storage"
        )
        
        if output.strip():
            with open(f"diffs/{'_'.join(map(lambda s: s[0:7], reversed(sha_list)))}_{label}.diff", "wb") as f:
                f.write(output)

topics = yaml.load(open("topics.yml").read(), Loader=yaml.Loader)['topics']

import pprint
pprint.pprint(topics)

diffs = defaultdict(list)
for fn in glob.glob("diffs/*.diff"):
    for frg in [p[0:7] for p in fn.split("_")[1:-1]]:
        diffs[frg].append(fn)

for k, vs in topics.items():
    print("Topic:", k)
    print("-----")
    print(vs.get("description", ""))
    
    topic_files = glob.glob(f"topics/{k}_*")
    if topic_files:
        print("Already processed, skipping")
        continue
    
    vs = vs["commits"]    
    vs_shas = [list(s.keys())[0] if isinstance(s, dict) else s for s in vs]
    vs_shas_vs = sorted(zip(vs_shas, vs), key=lambda s: -[sha.startswith(s[0]) for sha in shas].index(True))
    vs_shas, vs = zip(*vs_shas_vs)
    
    previous = None
    
    for fn in glob.glob("diffs/*.diff"):
        fn_parts = os.path.basename(fn).split("_")
        if vs_shas[0] in fn_parts[1:]:
            previous = fn_parts[0]
            break
            
    assert previous is not None
    
    shutil.rmtree("tmp/a", ignore_errors=True)
    shutil.rmtree("tmp/b", ignore_errors=True)
    
    previous = [x for x in os.listdir("storage") if x.startswith(previous)][0]
    
    print("base", previous)
    
    shutil.copytree(f"storage/{previous}", "tmp/a")
    shutil.copytree(f"storage/{previous}", "tmp/b")        
    
    for v in vs:
        
        if isinstance(v, dict):
            sha = list(v.keys())
            assert len(sha) == 1
            sha = sha[0]
        else:
            sha = v

        print(sha)
            
        for fn in diffs[sha]:
            print(fn)
            if isinstance(v, dict):                
                ps = unidiff.PatchSet.from_filename(fn)
                filter_fn = list(v.values())[0][0].get('file')
                
                if filter_fn:
                    if isinstance(filter_fn, str):
                        filter_fn = [filter_fn]
                
                    print(f"={filter_fn}")
                    files = [f for f in ps if any(ffn in f"{f.source_file}{f.target_file}" for ffn in filter_fn)]
                    print(len(files), "files")
                    ps = unidiff.PatchSet("".join(map(str, files)))
                    patch_content = str(ps)
                    
                filter_hunk = list(v.values())[0][0].get('hunk')
                
                if filter_hunk:
                    if isinstance(filter_hunk, str):
                        filter_hunk = [filter_hunk]
                        
                    print(f"@{filter_hunk}")
                    segments = []
                    for file in ps:
                        filtered = [hunk for hunk in file if any(fh in str(hunk) for fh in filter_hunk)]
                        print(len(filtered), "filtered")
                        if filtered:
                            segments.append(str(file).replace("".join(map(str, file)), ""))
                            segments.extend(map(str, filtered))
                            
                    patch_content = "".join(segments)
            else:
                patch_content = open(fn, encoding='utf-8').read()                
            
            if patch_content:
                run(
                    r"C:\Program Files\Git\usr\bin\patch.exe",
                    "-t",
                    "-N",
                    "-p1",
                    can_fail=False,
                    decode=None,
                    capture_output=False,
                    input=patch_content.encode('utf-8'),
                    cwd="tmp/b"
                )

    for art in (ARTEFACTS + ("IFC.exp.rej",)):
        output = run(
            r"C:\Program Files\Git\usr\bin\diff.exe",
            "-N",
            "-w",
            "-U10",
            f"tmp/a/{art}",
            f"tmp/b/{art}",
            can_fail=True,
            decode=None
        )
    
        if output.strip():
            with open(f"topics/{k}_{art}.patch", "wb") as f:
                f.write(output)

def publish_to_github():
    import os
    import time
    from github import Github

    g = Github(os.environ["GH_TOKEN"])
    r = g.get_repo("AECgeeks/infra-repo-issue-test-2")

    for topic, topic_dict in topics.items():
        desc = topic_dict.get("description", "")
        topic_files = glob.glob(f"topics/{topic}_*")
        topic = topic.replace("_", " ")

        print(topic)
        print("="*len(topic))
        issue = r.create_issue(topic, body=desc)
        time.sleep(30)
        
        for tf in topic_files:
            ps = unidiff.PatchSet.from_filename(tf)
            
            builder = ""
            
            def register_comment():
                print("\n".join(builder.split("\n")[0:3]))
                issue.create_comment(f"~~~diff\n{builder}~~~")
                time.sleep(30)            
            
            for pf in map(str, ps):            
                builder += pf
                if len(builder) > 10000:
                    register_comment()
                    builder = ""

            if builder:
                register_comment()

def publish_to_pdf():
   
    with open("pdf.md", "w") as doc:
    
        for topic, topic_dict in topics.items():
            desc = topic_dict.get("description", "")
            topic_files = glob.glob(f"topics/{topic}_*")
            topic = topic.replace("_", " ")
            topic = topic.replace("jwg12 ", "")
            
            print(r"""
---
title: IFC4.3 changes
author: Thomas Krijnen <tk@aecgeeks.com>
geometry: margin=3cm
mainfont: Lora-Regular.ttf
colorlinks: true
linkcolor: gray
urlcolor: gray
toccolor: gray
mainfontoptions:
- BoldFont=Lora-Bold.ttf
- ItalicFont=Lora-Italic.ttf
- BoldItalicFont=Lora-BoldItalic.ttf
header-includes: |
    \usepackage{fancyhdr}
    \pagestyle{fancy}
    \fancyhead[LO,LE]{IFC4.3 changes}
    \fancyfoot[CO,CE]{\today}
    \fancyfoot[RE,LO]{Thomas Krijnen <tk@aecgeeks.com>}
    \fancyfoot[LE,RO]{\raisebox{0.1cm}{\thepage}}
    \usepackage{pdfpages}
...
""", file=doc)

            print("#", topic, file=doc)
            print(file=doc)
            print(topic_dict.get("description", ""), file=doc)
            print(file=doc)
            
            for tf in topic_files:
                ps = unidiff.PatchSet.from_filename(tf)
                
                print("```diff", file=doc)
                print(ps, file=doc)
                print("```", file=doc)
            
    run(*"pandoc -o changes.pdf --toc --pdf-engine xelatex pdf.md".split(" "))

if "--github" in sys.argv:
    publish_to_github()
    
if "--pdf" in sys.argv:
    publish_to_pdf()
    