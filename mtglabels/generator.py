import argparse
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import cairosvg
import jinja2
import requests

log = logging.getLogger(__name__)

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))

ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(BASE_DIR / "templates"),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)

# Set types we are interested in
SET_TYPES = (
    "core",
    "expansion",
    "starter",  # Portal, P3k, welcome decks
    "masters",
    "commander",
    "planechase",
    "draft_innovation",  # Battlebond, Conspiracy
    "duel_deck",  # Duel Deck Elves,
    "premium_deck",  # Premium Deck Series: Slivers, Premium Deck Series: Graveborn
    "from_the_vault",  # Make sure to adjust the MINIMUM_SET_SIZE if you want these
    "archenemy",
    "box",
    "funny",  # Unglued, Unhinged, Ponies: TG, etc.
    # "memorabilia",  # Commander's Arsenal, Celebration Cards, World Champ Decks
    # "spellbook",
    # These are relatively large groups of sets
    # You almost certainly don't want these
    # "token",
    # "promo",
)

# Only include sets at least this size
# For reference, the smallest proper expansion is Arabian Nights with 78 cards
MINIMUM_SET_SIZE = 50

# Set codes you might want to ignore
IGNORED_SETS = (
    "cmb1",  # Mystery Booster Playtest Cards
    "amh1",  # Modern Horizon Art Series
    "cmb2",  # Mystery Booster Playtest Cards Part Deux
    "fbb",   # Foreign Black Border
    "sum",   # Summer Magic / Edgar
    "4bb",   # Fourth Edition Foreign Black Border
    "bchr",  # Chronicles Foreign Black Border
    "rin",   # Rinascimento
    "ren",   # Renaissance
    "rqs",   # Rivals Quick Start Set
    "itp",   # Introductory Two-Player Set
    "sir",   # Shadows over Innistrad Remastered
    "sis",   # Shadows of the Past
    "cst",   # Coldsnap Theme Decks
)

# Used to rename very long set names
RENAME_SETS = {
    "Fourth Edition Foreign Black Border": "Fourth Edition FBB",
    "Introductory Two-Player Set": "Intro Two-Player Set",
    "Commander Anthology Volume II": "Commander Anthology II",
    "Planechase Anthology Planes": "Planechase Anth. Planes",
    "Mystery Booster Playtest Cards": "Mystery Booster Playtest",
    "World Championship Decks 1997": "World Championship 1997",
    "World Championship Decks 1998": "World Championship 1998",
    "World Championship Decks 1999": "World Championship 1999",
    "World Championship Decks 2000": "World Championship 2000",
    "World Championship Decks 2001": "World Championship 2001",
    "World Championship Decks 2002": "World Championship 2002",
    "World Championship Decks 2003": "World Championship 2003",
    "World Championship Decks 2004": "World Championship 2004",
    "Duel Decks: Elves vs. Goblins": "DD: Elves vs. Goblins",
    "Duel Decks: Jace vs. Chandra": "DD: Jace vs. Chandra",
    "Duel Decks: Divine vs. Demonic": "DD: Divine vs. Demonic",
    "Duel Decks: Garruk vs. Liliana": "DD: Garruk vs. Liliana",
    "Duel Decks: Phyrexia vs. the Coalition": "DD: Phyrexia vs. Coalition",
    "Duel Decks: Elspeth vs. Tezzeret": "DD: Elspeth vs. Tezzeret",
    "Duel Decks: Knights vs. Dragons": "DD: Knights vs. Dragons",
    "Duel Decks: Ajani vs. Nicol Bolas": "DD: Ajani vs. Nicol Bolas",
    "Duel Decks: Heroes vs. Monsters": "DD: Heroes vs. Monsters",
    "Duel Decks: Speed vs. Cunning": "DD: Speed vs. Cunning",
    "Duel Decks Anthology: Elves vs. Goblins": "DDA: Elves vs. Goblins",
    "Duel Decks Anthology: Jace vs. Chandra": "DDA: Jace vs. Chandra",
    "Duel Decks Anthology: Divine vs. Demonic": "DDA: Divine vs. Demonic",
    "Duel Decks Anthology: Garruk vs. Liliana": "DDA: Garruk vs. Liliana",
    "Duel Decks: Elspeth vs. Kiora": "DD: Elspeth vs. Kiora",
    "Duel Decks: Zendikar vs. Eldrazi": "DD: Zendikar vs. Eldrazi",
    "Duel Decks: Blessed vs. Cursed": "DD: Blessed vs. Cursed",
    "Duel Decks: Nissa vs. Ob Nixilis": "DD: Nissa vs. Ob Nixilis",
    "Duel Decks: Merfolk vs. Goblins": "DD: Merfolk vs. Goblins",
    "Duel Decks: Elves vs. Inventors": "DD: Elves vs. Inventors",
    "Premium Deck Series: Slivers": "Premium Deck Slivers",
    "Premium Deck Series: Graveborn": "Premium Deck Graveborn",
    "Premium Deck Series: Fire and Lightning": "PD: Fire & Lightning",
    "Mystery Booster Retail Edition Foils": "Mystery Booster Retail Foils",
    "Adventures in the Forgotten Realms": "Forgotten Realms",
    "Archenemy: Nicol Bolas Schemes": "Archenemy: Bolas Schemes",
    "Global Series Jiang Yanggu & Mu Yanling": "Jiang Yanggu & Mu Yanling",
    "Mystery Booster Playtest Cards 2019": "MB Playtest Cards 2019",
    "Mystery Booster Playtest Cards 2021": "MB Playtest Cards 2021",
    "Strixhaven: School of Mages Minigames": "Strixhaven Minigames",
    "Adventures in the Forgotten Realms Minigames": "Forgotten Realms Minigames",
    "Innistrad: Crimson Vow Minigames": "Crimson Vow Minigames",
    "Commander Legends: Battle for Baldur's Gate": "CMDR Legends: Baldur's Gate",
    "Warhammer 40,000 Commander": "Warhammer 40K",
    "The Brothers' War Retro Artifacts": "Brothers' War Retro",
    "The Brothers' War Commander": "Brothers' War Commander",
    "Phyrexia: All Will Be One Commander": "Phyrexia: One CMDR",
}


class LabelGenerator:
    DEFAULT_OUTPUT_DIR = Path(os.getcwd()) / "output"

    COLS = 3
    ROWS = 10
    MARGIN = 40  # in 1/10 mm
    START_X = MARGIN
    START_Y = MARGIN + 40

    PAPER_SIZES = {
        "letter": {"width": 2160, "height": 2790, },  # in 1/10 mm
        "a4": {"width": 2100, "height": 2970, },
    }
    DEFAULT_PAPER_SIZE = "letter"

    def __init__(self, paper_size=None, output_dir=None):
        self.paper_size = paper_size or LabelGenerator.DEFAULT_PAPER_SIZE
        paper = self.PAPER_SIZES[paper_size]

        self.set_codes = []
        self.ignored_sets = IGNORED_SETS
        self.set_types = SET_TYPES
        self.minimum_set_size = MINIMUM_SET_SIZE

        self.width = paper["width"]
        self.height = paper["height"]

        # These are the deltas between rows and columns
        self.delta_x = (self.width - (2 * self.MARGIN)) / self.COLS + 10
        self.delta_y = (self.height - (2 * self.MARGIN)) / self.ROWS - 18

        self.output_dir = Path(output_dir or LabelGenerator.DEFAULT_OUTPUT_DIR)

    def generate_labels(self, sets=None):
        if sets:
            self.ignored_sets = ()
            self.minimum_set_size = 0
            self.set_types = ()
            self.set_codes = [exp.lower() for exp in sets]

        page = 1
        labels = self.create_set_label_data()
        while labels:
            exps = []
            while labels and len(exps) < (self.ROWS * self.COLS):
                exps.append(labels.pop(0))

            # Render the label template
            template = ENV.get_template("labels.svg")
            output = template.render(
                labels=exps,
                WIDTH=self.width,
                HEIGHT=self.height,
            )
            outfile_svg = self.output_dir / f"labels-{self.paper_size}-{page:02}.svg"
            outfile_pdf = str(
                self.output_dir / f"labels-{self.paper_size}-{page:02}.pdf"
            )

            log.info(f"Writing {outfile_svg}...")
            with open(outfile_svg, "w") as fd:
                fd.write(output)

            log.info(f"Writing {outfile_pdf}...")
            with open(outfile_svg, "rb") as fd:
                cairosvg.svg2pdf(
                    file_obj=fd, write_to=outfile_pdf, unsafe=True,
                )

            page += 1

    def get_set_data(self):
        log.info("Getting set data and icons from Scryfall")

        # https://scryfall.com/docs/api/sets
        # https://scryfall.com/docs/api/sets/all
        resp = requests.get("https://api.scryfall.com/sets")
        resp.raise_for_status()

        data = resp.json()["data"]
        set_data = []
        for exp in data:
            if exp["code"] in self.ignored_sets:
                continue
            elif exp["card_count"] < self.minimum_set_size:
                continue
            elif self.set_types and exp["set_type"] not in self.set_types:
                continue
            elif self.set_codes and exp["code"].lower() not in self.set_codes:
                # Scryfall set codes are always lowercase
                continue
            else:
                set_data.append(exp)

        # Warn on any unknown set codes
        if self.set_codes:
            known_sets = set([exp["code"] for exp in data])
            specified_sets = set([code.lower() for code in self.set_codes])
            unknown_sets = specified_sets.difference(known_sets)
            for set_code in unknown_sets:
                log.warning("Unknown set '%s'", set_code)

        set_data.reverse()
        return set_data

    def create_set_label_data(self):
        """
        Create the label data for the sets

        This handles positioning of the label's (x, y) coords
        """
        labels = []
        x = self.START_X
        y = self.START_Y

        # Get set data from scryfall
        set_data = self.get_set_data()

        for exp in set_data:
            name = RENAME_SETS.get(exp["name"], exp["name"])
            icon_url = exp["icon_svg_uri"]

            # Extract the filename from the URL and remove query parameters
            filename = os.path.basename(icon_url)
            filename = filename.split("?")[0]

            # Check if the file already exists
            os.makedirs("/tmp/mtglabels/svg", exist_ok=True)
            file_path = os.path.join("/tmp/mtglabels/svg", filename)
            if os.path.exists(file_path):
                # Skip downloading if the file exists and has the same size
                print(f"Skipping download. File already exists: {icon_url}")
                icon_filename = filename
            else:
                # Download svg set file
                response = requests.get(icon_url)
                if response.status_code == 200:
                    # Save the file in the 'output/svg' folder
                    with open(file_path, "wb") as file:
                        file.write(response.content)
                    icon_filename = filename
                else:
                    print(f"Failed to download file: {icon_url}")
                    icon_filename = None

            if icon_filename:
                shutil.copy(file_path, self.output_dir)
                labels.append(
                    {
                        "name": name,
                        "code": exp["code"],
                        "date": datetime.strptime(exp["released_at"], "%Y-%m-%d").date(),
                        "icon_filename": icon_filename,
                        "x": x,
                        "y": y,
                    }
                )

            y += self.delta_y

            # Start a new column if needed
            if len(labels) % self.ROWS == 0:
                x += self.delta_x
                y = self.START_Y

            # Start a new page if needed
            if len(labels) % (self.ROWS * self.COLS) == 0:
                x = self.START_X
                y = self.START_Y

        return labels


def main():
    log_format = '[%(levelname)s] %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO)

    parser = argparse.ArgumentParser(description="Generate MTG labels")

    parser.add_argument(
        "--output-dir",
        default=LabelGenerator.DEFAULT_OUTPUT_DIR,
        help="Output labels to this directory",
    )
    parser.add_argument(
        "--paper-size",
        default=LabelGenerator.DEFAULT_PAPER_SIZE,
        choices=LabelGenerator.PAPER_SIZES.keys(),
        help='Use this paper size (default: "letter")',
    )
    parser.add_argument(
        "sets",
        nargs="*",
        help=(
            "Only output sets with the specified set code (eg. MH1, NEO). "
            "This can be used multiple times."
        ),
        metavar="SET",
    )

    args = parser.parse_args()

    generator = LabelGenerator(args.paper_size, args.output_dir)
    generator.generate_labels(args.sets)


if __name__ == "__main__":
    main()
