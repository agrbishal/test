import subprocess
import pandas as pd

def run(cmd):
    return subprocess.check_output(cmd, shell=True).decode().strip()

branches = run("git for-each-ref --format='%(refname:short)' refs/remotes/origin").split("\n")

summary = []

writer = pd.ExcelWriter("git_branch_audit.xlsx", engine="xlsxwriter")

for branch in branches:

    if "HEAD" in branch:
        continue

    print("Processing:", branch)

    # last commit
    last = run(f'git log -1 --pretty=format:"%H|%an|%ad|%s" {branch}')
    last_hash, last_author, last_date, last_msg = last.split("|",3)

    # total commits
    total_commits = run(f"git rev-list --count {branch}")

    # first commit
    first = run(f'git log {branch} --reverse --pretty=format:"%H|%an|%ad|%s" | head -1')
    f_hash, f_author, f_date, f_msg = first.split("|",3)

    # try estimating parent branch
    parent = "unknown"
    try:
        parent = run(f"git merge-base {branch} origin/master")
    except:
        pass

    summary.append({
        "Branch": branch,
        "Last Commit Date": last_date,
        "Last Author": last_author,
        "Last Commit Message": last_msg,
        "Total Commits": total_commits,
        "First Commit Date": f_date,
        "First Commit Author": f_author,
        "First Commit Message": f_msg,
        "Possible Parent Commit": parent
    })

    # commit history
    log = run(f'git log {branch} --pretty=format:"%ad|%an|%H|%s" --date=iso')

    rows = []
    for line in log.split("\n"):
        date, author, commit, msg = line.split("|",3)
        rows.append({
            "Date": date,
            "Author": author,
            "Commit": commit,
            "Message": msg
        })

    df = pd.DataFrame(rows)

    sheet = branch.replace("origin/","")[:31]
    df.to_excel(writer, sheet_name=sheet, index=False)

summary_df = pd.DataFrame(summary)
summary_df.to_excel(writer, sheet_name="Branch Summary", index=False)

writer.close()

print("Report generated: git_branch_audit.xlsx")
