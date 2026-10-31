import json
import os
import subprocess
import time


def railway(*arguments):
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("GITHUB_")
    }
    result = subprocess.run(
        ["railway", *arguments], capture_output=True, text=True,
        timeout=600, env=environment,
    )
    if result.returncode:
        raise SystemExit("Deployment command failed. Inspect the hosting dashboard.")
    return result.stdout


def main():
    project = os.environ["RAILWAY_PROJECT_ID"]
    environment = os.environ["RAILWAY_ENVIRONMENT_ID"]
    services = {
        "Application": os.environ["RAILWAY_SERVER_SERVICE_ID"],
        "Worker": os.environ["RAILWAY_WORKER_SERVICE_ID"],
    }

    def deployments(service):
        return json.loads(
            railway(
                "deployment", "list", "--project", project,
                "--environment", environment, "--service", service,
                "--limit", "20", "--json",
            )
        )

    pending = {}
    for label, service in services.items():
        railway(
            "up", "--project", project, "--environment", environment,
            "--service", service, "--detach", "--yes",
        )
        pending[label] = deployments(service)[0]["id"]
        print(f"{label}: submitted", flush=True)

    deadline = time.monotonic() + 30 * 60
    previous = {}
    while pending:
        if time.monotonic() >= deadline:
            raise SystemExit("Deployment timed out. Inspect the hosting dashboard.")
        for label, deployment_id in list(pending.items()):
            deployment = next(
                (item for item in deployments(services[label])
                 if item["id"] == deployment_id),
                None,
            )
            if deployment is None:
                raise SystemExit(f"{label}: deployment is no longer available.")
            status = deployment["status"]
            if previous.get(label) != status:
                print(f"{label}: {status}", flush=True)
                previous[label] = status
            if status == "SUCCESS":
                del pending[label]
            elif status in {"FAILED", "CRASHED", "REMOVED", "SKIPPED"}:
                raise SystemExit(f"{label}: deployment failed. Inspect the hosting dashboard.")
        if pending:
            time.sleep(15)


if __name__ == "__main__":
    main()
