#!/usr/bin/env python3
"""Check Asana for incomplete tasks and send message to Ed."""

import os
import json
import subprocess

ASANA_TOKEN = os.environ.get("ASANA_API_KEY", "2/1207192071661358/1213723137528929:e99deaba969da3f30a3bbcb801a24bd9")
WORKSPACE_ID = "1207191902925072"

def get_projects():
    """Get all projects."""
    import urllib.request
    req = urllib.request.Request(
        f"https://app.asana.com/api/1.0/workspaces/{WORKSPACE_ID}/projects?opt_fields=name",
        headers={"Authorization": f"Bearer {ASANA_TOKEN}"}
    )
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        return {p["gid"]: p["name"] for p in data.get("data", [])}

def get_incomplete_tasks(project_gid):
    """Get incomplete tasks for a project."""
    import urllib.request
    req = urllib.request.Request(
        f"https://app.asana.com/api/1.0/projects/{project_gid}/tasks?opt_fields=name,completed&archived=false",
        headers={"Authorization": f"Bearer {ASANA_TOKEN}"}
    )
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        return [t["name"] for t in data.get("data", []) if not t.get("completed", True)]

def send_message(text):
    """Send message via OpenClaw."""
    result = subprocess.run(
        ["openclaw", "message", "send", "--channel", "telegram", "--target", "7641700722", "--message", text],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def main():
    projects = get_projects()
    all_tasks = []
    
    for gid, name in projects.items():
        tasks = get_incomplete_tasks(gid)
        if tasks:
            all_tasks.append((name, tasks))
    
    if not all_tasks:
        message = "No incomplete tasks in Asana."
    else:
        message = "📋 *Incomplete Tasks*\n\n"
        for project, tasks in all_tasks:
            message += f"*{project}*\n"
            for t in tasks:
                message += f"○ {t}\n"
            message += "\n"
    
    # Send the message
    success = send_message(message)
    
    if success:
        print("Message sent successfully.")
    else:
        print("Failed to send message.")

if __name__ == "__main__":
    main()
