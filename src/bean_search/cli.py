"""Command line entry point: `bean-search build` / `bean-search info`."""

import argparse
import json
import logging
from pathlib import Path

from . import cache, config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="bean-search")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="download data and build the bean graph")
    b.add_argument("--region", choices=sorted(config.REGIONS), default=config.DEFAULT_REGION)
    b.add_argument("--out", type=Path, help="output path (default: data/<region>_bean_graph.pkl)")
    b.add_argument("--no-landmark-links", action="store_true", help="skip virtual long-haul edges")

    i = sub.add_parser("info", help="summarize a built graph")
    i.add_argument("path", type=Path)

    s = sub.add_parser("search", help="collect the most beans within N moves")
    s.add_argument("--graph", type=Path, default=cache.default_path(config.DEFAULT_REGION))
    s.add_argument("--lat", type=float, required=True)
    s.add_argument("--lon", type=float, required=True)
    s.add_argument("--moves", type=int, default=150)
    s.add_argument("--width", type=int, default=8, help="beam width")
    s.add_argument("--branch", type=int, default=4, help="beans tried per state")

    v = sub.add_parser("serve", help="run the bean map UI")
    v.add_argument("--graph", type=Path, default=cache.default_path(config.DEFAULT_REGION))
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.cmd == "build":
        from .graph import build_bean_graph, summarize  # heavy import

        G = build_bean_graph(args.region, connect_landmarks=not args.no_landmark_links)
        out = cache.save_graph(G, args.out or cache.default_path(args.region))
        print(json.dumps(summarize(G), indent=2))
        print(f"saved -> {out}")
    elif args.cmd == "info":
        from .graph import summarize

        print(json.dumps(summarize(cache.load_graph(args.path)), indent=2))
    elif args.cmd == "search":
        from .search import BeanSearcher

        G = cache.load_graph(args.graph)
        searcher = BeanSearcher(G)
        start = searcher.nearest_road_node(args.lat, args.lon)
        res = searcher.search(start, args.moves, width=args.width, branch=args.branch)
        print(f"{len(res.goals)} beans in {res.moves}/{args.moves} moves ({res.meters / 1000:.1f} km)")
        for n, g in enumerate(res.goals, 1):
            d = G.nodes[g]
            print(f"  {n:>3}. [{d['bean_type']}] {d.get('name') or '(unnamed)'}")
    elif args.cmd == "serve":
        from .server import serve

        serve(cache.load_graph(args.graph), args.host, args.port)


if __name__ == "__main__":
    main()
