#!/usr/bin/env python

"""
Copyright (c) 2018, salesforce.com, inc.
All rights reserved.
SPDX-License-Identifier: BSD-3-Clause
For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause


The pomgen cmdline entry-point.
"""

from common import argsupport
from common import common
from common import logger
from common import mdfiles
from config import config
from crawl import crawler
from crawl import pom
from crawl import workspace
import argparse
import os
import re
import sys

def _parse_arguments(args):
    parser = argparse.ArgumentParser(description="Monorepo Pom Generator")
    parser.add_argument("--package", type=str, required=True,
        help="Narrows pomgen to the specified package(s). " + argsupport.get_package_doc())
    parser.add_argument("--destdir", type=str, required=True,
        help="The root directory generated poms are written to")
    parser.add_argument("--repo_root", type=str, required=False,
        help="The root of the repository")
    parser.add_argument("--recursive", required=False, action='store_true',
        help="Also generate poms for dependencies, disabled by default")
    parser.add_argument("--force", required=False, action='store_true',
        help="If set, always generated poms, regardless of whether an artifact has changed since it was last released")
    parser.add_argument("--pom_goldfile", required=False, action='store_true',
        help="Generates a goldfile pom")
    parser.add_argument("--verbose", required=False, action='store_true',
        help="Verbose output")
    return parser.parse_args(args)

def _get_output_dir(args):
    if not args.destdir:
        return None
    if not os.path.exists(args.destdir):
        os.makedirs(args.destdir)
    if not os.path.isdir(args.destdir):
        raise Exception("[%s] is not a directory %s" % args.out)
    destdir = os.path.realpath(args.destdir)
    logger.info("Output dir [%s]" %  destdir)
    return destdir

def main(args):
    args = _parse_arguments(args)
    repo_root = common.get_repo_root(args.repo_root)
    cfg = config.load(repo_root, args.verbose)
    ws = workspace.Workspace(repo_root, cfg.external_dependencies, 
                             cfg.excluded_dependency_paths,
                             cfg.all_src_exclusions)

    packages = argsupport.get_all_packages(repo_root, args.package)
    packages = ws.filter_artifact_producing_packages(packages)
    if len(packages) == 0:
        raise Exception("Did not find any artifact producing BUILD.pom packages at [%s]" % args.package)
    spider = crawler.Crawler(ws, cfg.pom_template, args.verbose)
    result = spider.crawl(packages,
                          follow_monorepo_references=args.recursive,
                          force=args.force)

    if len(result.pomgens) == 0:
        logger.info("No releases are required. pomgen will not generate any pom files. To force pom generation, use pomgen's --force option.")
    else:
        output_dir = _get_output_dir(args)

        for pomgen in result.pomgens:
            pom_dest_dir = os.path.join(output_dir, pomgen.bazel_package)
            if not os.path.exists(pom_dest_dir):
                os.makedirs(pom_dest_dir)

            genmode = pom.PomContentType.GOLDFILE if args.pom_goldfile else pom.PomContentType.RELEASE
            pom_content = pomgen.gen(genmode)

            # the goldfile pom is actually a pomgen metadata file, so we 
            # write it using the mdfiles module, which ensures it goes 
            # into the proper location within the specified bazel package
            if args.pom_goldfile:
                pom_goldfile_path = mdfiles.write_file(pom_content, output_dir, pomgen.bazel_package, mdfiles.POM_XML_RELEASED_FILE_NAME)
                logger.info("Wrote pom goldfile to [%s]" % pom_goldfile_path)
            else:
                pom_path = os.path.join(pom_dest_dir, "pom.xml")
                with open(pom_path, "w") as f:
                    f.write(pom_content)
                logger.info("Wrote pom file to [%s]" % pom_path)

if __name__ == "__main__":
    main(sys.argv[1:])
