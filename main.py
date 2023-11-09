#!/usr/bin/python

import os
import json
import time
import requests
import argparse
import frontmatter

ABS_PATH = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(ABS_PATH, "config.json")

with open(CONFIG_FILE) as config_file:
    config = json.load(config_file)

API_URL = config["api_url"]
API_KEY = config["api_key"]


class GraphQLClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key

    def send_query(self, query):
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        response = requests.post(self.api_url, json={'query': query}, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f'Error: {response.status_code}\n{response.text}')

    def create_page(self, title, path, content, description):
        escaped_content = json.dumps(content)
        query = f"""
            mutation {{
              pages {{
                create(
                  content: {escaped_content},
                  description: "{description}",
                  editor: "markdown",
                  isPublished: true,
                  isPrivate: false,
                  locale: "fr",
                  path: "{path}",
                  tags: ["infra"],
                  title: "{title}"
                ) {{
                  responseResult {{
                    succeeded
                    errorCode
                    slug
                    message
                  }}
                }}
              }}
            }}
        """
        return self.send_query(query)

    def get_page(self, path):
        query = f"""
            query {{
              pages {{
                singleByPath(path: "{path}", locale: "fr") {{
                  title
                  id
                  description
                  path
                  content
                  tags {{
                    tag 
                  }}
                }}
              }}
            }}
        """
        return self.send_query(query)["data"]["pages"]["singleByPath"]

    def delete_page(self, id):
        query = f"""
            mutation {{
              pages {{
                delete(id: {int(id)}) {{
                  responseResult {{
                    succeeded
                    errorCode
                    slug
                    message
                  }}
                }}
              }}
            }}
        """
        return self.send_query(query)


def create_md_file_from_path(path: str, output: str):
    client = GraphQLClient(API_URL, API_KEY)
    page = client.get_page(path)
    metadata = {
        "title": page["title"],
        "description": page["description"],
        "path": page["path"],
        "tags": page["tags"]
    }
    content = page["content"]
    md = frontmatter.Post(content, metadata=metadata)
    with open(output, "w") as f:
        f.write(frontmatter.dumps(md))


def create_md_file(file, output: str):
    metadata = {
        "title": file["title"],
        "description": file["description"],
        "path": file["path"],
        "tags": file["tags"]
    }
    content = file["content"]
    md = frontmatter.Post(content, metadata=metadata)
    with open(output, "w") as f:
        f.write(frontmatter.dumps(md))


def main():
    parser = argparse.ArgumentParser(description="Manage Wiki pages")
    parser.add_argument("action", choices=["create", "get", "delete", "update"], help="Action to perform")
    parser.add_argument("-f", "--file", help="Input Markdown file for create action")
    parser.add_argument("-o", "--output", help="Output Markdown file for get action")
    parser.add_argument("-p", "--path", help="Page path for get and delete actions")

    args = parser.parse_args()

    client = GraphQLClient(API_URL, API_KEY)

    if args.action == "create":
        if not args.file:
            parser.error("The --file option is required for the 'create' action")
        page = frontmatter.load(args.file)
        content, metadata = page.content, page.metadata["metadata"]
        response = client.create_page(metadata["title"], metadata["path"], content, metadata["description"])
        print(response)

    elif args.action == "get":
        if not args.path:
            parser.error("The --path option is required for the 'get' action")
        if not args.output:
            output = args.path.split("/")[-1] + '.md'
            create_md_file_from_path(args.path, output)
            print(f"File '{output}' created with content and metadata.")
        else:
            create_md_file_from_path(args.path, args.output)
            print(f"File '{args.output}' created with content and metadata.")

    elif args.action == "delete":
        if not args.path:
            parser.error("The --path option is required for the 'delete' action")
        page = client.get_page(args.path)
        response = client.delete_page(page["id"])
        print(response)

    elif args.action == "update":
        if not args.file:
            parser.error("The --file is required for the 'update' action")
        page = frontmatter.load(args.file)
        content, metadata = page.content, page.metadata["metadata"]
        path = metadata["path"]
        wiki_page = client.get_page(path)
        id = wiki_page["id"]
        backup = '.backup/' + '/'.join(path.split('/')[:-1])
        if not os.path.exists(backup):
            os.makedirs(backup)
        output = backup + '/' + path.split('/')[-1] + '-' + time.strftime("%Y%m%d-%H%M%S") + '.md'
        create_md_file(wiki_page, output)
        client.delete_page(id)
        client.create_page(metadata["title"], metadata["path"], content, metadata["description"])
        print(f"File '{path}' updated.")


if __name__ == "__main__":
    main()
