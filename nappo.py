#!/usr/bin/env python3.6

# Copyright © 2021 Red Hat, Inc
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# nappo: a chocolate covered nougat

import argparse
from collections import namedtuple
import json
import os
import packaging.version
import sys
from typing import Any, Dict, List, Optional
import urllib.parse, urllib.request

REPOSITORIES = {
    # generated by running this command on the source-build source tree:
    # grep -Ir 'v3/index.json' | grep -Eo "(http|https)://[a-zA-Z0-9./?=_%:-]*" | tr 'A-Z' 'a-z' | sort -u

    # dotnet-core has an expired certificate
    # "dotnet-core": "https://dotnet.myget.org/F/dotnet-core/api/v3/index.json",
    "dotnet5": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet5/nuget/v3/index.json",
    "dotnet5-transport": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet5-transport/nuget/v3/index.json",
    "dotnet6": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet6/nuget/v3/index.json",
    "dotnet6-transport": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet6-transport/nuget/v3/index.json",
    "dotnet7": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet7/nuget/v3/index.json",
    "dotnet7-transport": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet7-transport/nuget/v3/index.json",
    "dotnet-eng": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-eng/nuget/v3/index.json",
    "dotnet-experimental": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-experimental/nuget/v3/index.json",
    "dotnet-libraries": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-libraries/nuget/v3/index.json",
    "dotnet-libraries-transport": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-libraries-transport/nuget/v3/index.json",
    "dotnet-public": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-public/nuget/v3/index.json",
    "dotnet-public-local": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-public%40local/nuget/v3/index.json",
    "dotnet-tools": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-tools/nuget/v3/index.json",
    "dotnet-tools-transport": "https://pkgs.dev.azure.com/dnceng/public/_packaging/dotnet-tools-transport/nuget/v3/index.json",
    "messagepack-csharp": "https://pkgs.dev.azure.com/ils0086/messagepack-csharp/_packaging/messagepack-ci/nuget/v3/index.json",
    "myget-applicationinsights": "https://www.myget.org/f/applicationinsights/api/v3/index.json",
    "myget-aspnet-contrib": "https://www.myget.org/f/aspnet-contrib/api/v3/index.json",
    "nuget.org": "https://api.nuget.org/v3/index.json",
}

Package = namedtuple('Package', ['name', 'version', 'repository'])

def main(argv: List[str]) -> int:

    parser = argparse.ArgumentParser(description='Work with NuGet repositories, with a focus on searching and finding obscure/internal packages.')

    parent_parser = argparse.ArgumentParser(add_help=False)

    repo_group = parent_parser.add_mutually_exclusive_group()
    repo_group.add_argument('--repository', help='search this nuget repository')
    repo_group.add_argument('--repository-list', help='search nuget repositories listed in this file')

    parent_parser.add_argument('--verbose', action='store_true', help='verbose output')

    subparsers = parser.add_subparsers(title='commands')  # requires is not provided in older versions

    list_repos_parser = subparsers.add_parser('list-repositories', parents=[parent_parser])
    list_repos_parser.set_defaults(func=list_repositories_command)

    search_parser = subparsers.add_parser('search', parents=[parent_parser])
    search_parser.add_argument('package_name', metavar='package-name',
                               type=str)
    search_parser.add_argument('package_version', metavar='package-version', default='', nargs='?')
    search_parser.set_defaults(func=search_command)

    download_parser = subparsers.add_parser('download', parents=[parent_parser])
    download_parser.add_argument('package_name', metavar='package-name',
                                 type=str)
    download_parser.add_argument('package_version', metavar='package-version', default='', nargs='?',
                                 type=str)
    download_parser.set_defaults(func=download_command)

    args = parser.parse_args()

    # print(args)

    if not hasattr(args, 'func'):
        print("Sorry function is required, to get current function invoke with --help")
        exit(1)
    args.func(args)

    return 0

def download_command(args):
    package_name = args.package_name
    package_version = args.package_version or None

    repository_urls = repositories_from_args(args)

    packages = []
    for repo in repository_urls:
        packages.extend(package_search(repo, package_name, package_version))

    # print(packages)
    if len(packages) > 1:
        packages = sorted(packages, key=lambda p: version_sort_key(p.version))

    package = packages[0]
    # print(package)

    # See https://docs.microsoft.com/en-us/nuget/api/package-base-address-resource#download-package-content-nupkg
    j = get_json(package.repository)
    resources = j['resources']
    content_service_url: str
    for r in resources:
        if r['@type'].startswith('PackageBaseAddress/3.0'):
            content_service_url = r['@id']

    if not content_service_url:
        print(f'error: unable to find a content service at {repository_url}')
        return []

    # print(search_service_url)

    download_url = f'{content_service_url}/{package.name}/{package.version}/{package.name.lower()}.{package.version.lower()}.nupkg'

    if args.verbose:
        print(download_url)

    filename = os.path.basename(download_url)

    urllib.request.urlretrieve(download_url, filename=filename)

    print(f'{filename}')

def list_repositories_command(args) -> None:
    for k, v in REPOSITORIES.items():
        print(f'{v} (alias: {k})')

def search_command(args) -> None:
    package_name = args.package_name
    package_version = args.package_version or None

    repository_urls = repositories_from_args(args)

    results = []

    for repo in repository_urls:
        results.extend(package_search(repo, package_name, package_version))

    results = sorted(results, key=lambda p: version_sort_key(p.version))

    for result in results:
        print(result)

def package_search(repository_url: str, package_name: str, package_version: Optional[str]) -> List[Package]:
    assert package_name is not None
    assert package_name != ''
    assert package_version != ''

    j = get_json(repository_url)
    if not j:
        return []
    # print(j)
    resources = j['resources']
    search_service_url: str
    for r in resources:
        if r['@type'].startswith('SearchQueryService/3.0'):
            search_service_url = r['@id']

    if not search_service_url:
        print(f'error: unable to find a search service at {repository_url}')
        return []

    # print(search_service_url)

    search_string = f'{search_service_url}?q={package_name}&prerelease=true&semVerLevel=2.0.0'

    # print(search_string)

    j = get_json(search_string)
    # print(j)
    if not j:
        return []

    result = []

    data=j['data']
    for package in sorted(data, key=lambda p: p['id']):
        versions = package['versions']
        versions = sorted(versions, key=lambda v: version_sort_key(v['version']))
        for version in versions:
            if package_version:
                if version_matches(version['version'], package_version):
                    # print(repository_url)
                    # print(version)
                    result.append(Package(f'{version["@id"]}', f'{version["version"]}', repository_url))
            else:
                result.append(Package(f'{version["@id"]}', f'{version["version"]}', repository_url))

    return result

def repositories_from_args(args) -> List[str]:
    if args.repository:
        repository_urls = [ get_repository_url(args.repository) ]
    elif args.repository_list:
        with open(args.repository_list) as f:
            repository_urls = [ line.strip() for line in f ]
    else:
        repository_urls = list(REPOSITORIES.values())
    return repository_urls

def get_repository_url(repository: Optional[str]) -> str:
    if (repository):
        if repository in REPOSITORIES.keys():
            repository_url = REPOSITORIES[repository]
        else:
            repository_url = repository
    else:
        repository_url = REPOSITORIES['nuget.org']

    return repository_url

def get_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(url) as f:
            return json.load(f)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None

def version_sort_key(version: str):
    return packaging.version.parse(version)

def version_matches(version: str, exact_or_pattern: str):
    return (version == exact_or_pattern) \
           or (exact_or_pattern.endswith('*') and version.startswith(exact_or_pattern[:-1]))

if __name__ == '__main__':
    sys.exit(main(sys.argv))
