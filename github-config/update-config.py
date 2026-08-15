import argparse
import json
import os
import requests
import sys

class Config:
    def get_changed_fields(self):
        fields = { }
        for key, value in self.config.items():
            github_value = self.github_config[key]
            if value != github_value:
                fields[key] = (value, github_value)
        return fields

class Resource:
    def __init__(self, parameters, reference):
        self.parameters = parameters
        self.reference = reference
        self.api_update_fn = requests.patch


    def check(self, token):
        remote_config = self.get_remote_config(token)
        if remote_config == self.reference:
            return None
        return remote_config


    def get_remote_config(self, token):
        headers = {
            "Accept" : "application/vnd.github+json",
            "Authorization" : f"Bearer {token}",
            "X-GitHub-Api-Version" : "2026-03-10"
        }
        r = requests.get(f"https://api.github.com/{self.api_get_uri}", headers = headers)
        return r.json()


    def update(self, token):
        headers = {
            "Accept" : "application/vnd.github+json",
            "Authorization" : f"Bearer {token}",
            "X-GitHub-Api-Version" : "2026-03-10"
        }

        print(f"{self.api_update_uri} : {self.parameters}")
        r = self.api_update_fn(
                f"https://api.github.com/{self.api_update_uri}",
                headers = headers,
                data = json.dumps(self.parameters))
        print(r)

class RunnerGroup(Resource):
    def __init__(self, parameters, reference):
        super().__init__(parameters, reference)
        self.api_get_uri = f"/orgs/llvm/actions/runner-groups/{self.reference["id"]}"


class RunnerGroupRepositories(Resource):
    def __init__(self, parameters, reference, runner_group):
        super().__init__(parameters, reference)
        self.runner_group = runner_group
        self.api_update_fn = requests.put
        self.api_update_uri = f"/orgs/llvm/actions/runner-groups/{self.runner_group["id"]}/repositories"
        self.api_get_uri = f"/orgs/llvm/actions/runner-groups/{self.runner_group["id"]}/repositories"

    def get_remote_config(self, token):
        r = super().get_remote_config(token)
        return r["repositories"]
    

def update_runner_groups(token):
    definitions = [
        "llvm-premerge-cluser-us-central.json"
    ]
    runner_groups = []
    # Load the definitions
    for filename in definitions:
        runner_groups.append(RunnerGroup(filename, token))

    for runner_group in runner_groups:
        print(f"Checking {runner_group.config["name"]}")
        changed_fields = runner_group.get_changed_fields()
        if changed_fields:
            for key, value in changed_fields.items():
                print(f"Key {key} differs local {value[0]} remote {value[1]}")


def path_to_object(path):
    with open(os.path.join(path, "reference.json")) as f:
        reference_json = json.load(f)
    with open(os.path.join(path, "inputs.json")) as f:
        input_json = json.load(f)
    if "runner-groups" in path:
        if "repositories" in path:
            with open(os.path.join(path, "..", "reference.json")) as f:
                runner_group_reference = json.load(f)
            return RunnerGroupRepositories(parameters = input_json, reference = reference_json, runner_group = runner_group_reference)
        else:
            return RunnerGroup(parameters = input_json, reference = reference_json)


def check_all(token):
    ret = True
    for root, dirs, files in os.walk("data"):
        if "reference.json" not in files:
            continue
        checker = path_to_object(root)
        remote_config = checker.check(token)
        if not remote_config:
            print(root, "no changes")
        else:
            ret = False
            print(root, "changed:")
            print("Local:")
            print(json.dumps(checker.reference, indent = 2))
            print("Remote:")
            print(json.dumps(remote_config, indent = 2))
    return ret

def update(token, resource_path):
    # We need to ensure the current configs are up to date, because some
    # updates can modify multiple resources and we want to be able
    # to ensure that any changes we see after the update were caused by
    # the update.
    print("Checking current configs")
    if not check_all(token):
        print ("Consistency check failed")
        return False

    print(f"Updating {resource_path}")
    resource = path_to_object(resource_path)
    resource.update(token)
    check_all(token)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token")
    parser.add_argument("--resource")
    parser.add_argument(
        "command",
        type=str,
        choices=[
            "check",
            "update"
        ],
    )

    args = parser.parse_args()

    if args.command == "check":
        check_all(args.token)
    elif args.command == "update":
        update(args.token, args.resource)


if __name__ == "__main__":
    main()
