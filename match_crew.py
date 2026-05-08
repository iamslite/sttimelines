#!/usr/bin/env python3
#
#  Copyright 2026 Alistair MacDonald // Slite Systems
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
import csv
import itertools
import json
import sys

from copy import deepcopy, copy
from typing import Iterable


DUPLICATED_TRAITS = {
    "doctor": "physician",
    "augments": "augment",
    "kca": "klingon-cardassian alliance",
    "sona": "son'a",
    "lotian": "iotian",
    "q": "q continuum",
    "jnaii": "j'naii",
    "ramatis 3 native": "ramatis iii native",
    "loqueeque": "loque'eque",
    "m113 creature": "m-113 creature",
    "rongovian": "r'ongovian",
    "jemhadar": "jem'hadar",
    "elaurian": "el-aurian",
    "baul": "ba'ul",
    "baku": "ba'ku",
    "section31": "section 31",
}


def _handle_duplicated_traits(trait_name: str) -> str:
    if trait_name in DUPLICATED_TRAITS:
        return DUPLICATED_TRAITS[trait_name]

    return trait_name


class Traits:
    def __init__(self, traits: Iterable):
        self._traits = []

        num_unknowns = 0

        for trait in traits:
            the_trait = (
                None if not trait else str(trait).strip().lower().replace("_", " ")
            )

            the_trait = _handle_duplicated_traits(the_trait)

            if not the_trait or the_trait == "?":
                num_unknowns += 1
            elif the_trait not in self._traits:
                self._traits.append(the_trait)

        self._traits.sort()
        self._traits.extend([None] * num_unknowns)

    def __hash__(self):
        return hash(";".join(self._traits))

    def __str__(self):
        return f"{', '.join([str(trait).capitalize() for trait in self._traits])}"

    def __repr__(self):
        return f"({str(self)})"

    def __eq__(self, other):
        if not isinstance(other, Traits):
            return NotImplemented

        return self.__hash__() == other.__hash__()

    def __contains__(self, item):
        if not isinstance(item, Traits) and not isinstance(item, str):
            return False

        filtered_traits = (
            list(filter(None, item)) if isinstance(item, Traits) else [item]
        )

        return len(filtered_traits) <= len(self) and all(
            [trait in self._traits for trait in filtered_traits]
        )

    def __len__(self):
        return len(self._traits)

    def __iter__(self):
        return iter(self._traits)

    @property
    def known_traits(self):
        return list(filter(None, self._traits))

    @property
    def num_known_traits(self):
        return len(self.known_traits)

    @property
    def num_unknown_traits(self):
        return len(self._traits) - self.num_known_traits


class Crewmember:
    def __init__(self, crewmember: dict):
        self._raw = crewmember
        self._traits = Traits(crewmember["traits"])

    def __getattr__(self, name):
        return self._raw.get(name)

    def __getitem__(self, name):
        return self._raw.get(name)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self._raw["name"]

    def __hash__(self):
        return hash(self._raw["name"].lower())

    def has_traits(self, traits: Traits):
        return traits in self._traits

    def __eq__(self, item):
        if isinstance(item, Crewmember) and item is self:
            return True

        try:
            str_item = str(item)
            return str_item.lower() == str(self).lower()
        except:
            pass

        return NotImplemented


class Roster:
    def __init__(self, crew: set[Crewmember] | list[Crewmember]):
        self.crew = crew if isinstance(crew, set) else set(crew)

    def __contains__(self, item) -> bool:
        items_set = set(item) if isinstance(item, str) else item

        try:
            flattened_items = set([str(crewmember).lower() for crewmember in items_set])
            flattened_crew = set([str(crewmember).lower() for crewmember in self.crew])

            intersect = flattened_crew & flattened_items

            return len(intersect) > 0
        except:
            pass

        return False

    def __bool__(self):
        return len(self.crew) > 0

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"{'; '.join([str(crewmember) for crewmember in self.crew])}" if self.crew else "None"

    def __len__(self):
        return len(self.crew)

    def __iter__(self):
        return iter(self.crew)


class Occurrence:
    def __init__(self, slot: str, crewmember: Crewmember, traits: Traits):
        self.slot = slot
        self.crewmember = crewmember
        self.traits = traits

    def __eq__(self, item):
        if not isinstance(item, Occurrence):
            return NotImplemented

        return (
            item.slot == self.slot
            and item.crewmember == self.crewmember
            and item.traits == self.traits
        )

    def __hash__(self):
        return hash(f"{self.slot};{self.crewmember};{self.traits}")


class Node:
    def __init__(self, name: str, traits: Traits|list[str]):
        self.name = name
        self.traits = traits if isinstance(traits, Traits) else Traits(traits)
        self.rosters = None

    def __iter__(self):
        return iter(self.rosters or [])

    def __len__(self):
        return len(self.rosters) if self.rosters else 0

    def __bool__(self):
        return self.traits.num_unknown_traits > 0

    def __repr__(self):
        return f"{self.name}: [{self.traits}] => {self.rosters}\n"


def parse_csv_string(csv_data: str) -> str:
    if not csv_data:
        return []

    for row in csv.reader([csv_data], delimiter=";"):
        return row


def filter_crew_for_level(level: int, crew: list) -> list:
    return [crewmember for crewmember in crew if crewmember["max_rarity"] <= level]


def filter_rosters_by_exclusions(
    rosters: dict[Roster],
    exclude: set[str]
) -> dict[Roster]:
    return {
        trait: roster for (trait, roster) in rosters.items() if exclude not in roster
    }


def is_roster_count_in_range(
    roster: Roster,
    min_length: int = 1,
    max_length: int | None = None,
) -> bool:
    roster_length = len(roster)

    if roster_length < min_length:
        return False

    if max_length and roster_length > max_length:
        return False

    return True


def filter_rosters_by_count(
    rosters: list[Roster],
    min_length: int = 1,
    max_length: int | None = None,
) -> dict[Roster]:
    return {
        traits: roster for (traits, roster) in rosters.items() if is_roster_count_in_range(
            roster,
            min_length,
            max_length,
        )
    }


def filter_singletons_from_node(
    node: Node,
    node_index: int,
    nodes: list[Node],
) -> Node:
    filtered_node = copy(node)

    filtered_node.rosters = filter_rosters_by_count(filtered_node.rosters, 2)

    return filtered_node


def filter_empty_from_node(
    node: Node,
    node_index: int,
    nodes: list[Node],
) -> Node:
    filtered_node = copy(node)

    filtered_node.rosters = filter_rosters_by_count(filtered_node.rosters, 1)

    return filtered_node


def filter_exclusions_from_node(
    node: Node,
    node_index: int,
    nodes: list[Node],
) -> Node:
    filtered_node = copy(node)

    filtered_node.rosters = filter_rosters_by_exclusions(filtered_node.rosters, exclusions)

    return filtered_node


def filter_nodes(nodes: list[Node], filters: list) -> list[Node]:
    filtered_nodes = nodes

    for filter in filters:
        filtered_nodes = [
            filter(node, index, filtered_nodes) for (index, node) in enumerate(filtered_nodes)
        ]

    return filtered_nodes


def find_trait_combinations(possible_traits: list, num_missing_traits) -> set:
    combinations = set()

    for trait in possible_traits:
        combinations.update(
            [
                Traits(traits)
                for traits in _build_trait_combinations(
                    [(trait,)],
                    set(possible_traits) - set([trait]),
                    num_missing_traits - 1,
                )
            ]
        )

    return combinations


def _build_trait_combinations(
    combinations: list, possible_traits: set, num_missing_traits: int
) -> list:
    if num_missing_traits < 1:
        return combinations

    new_combinations = []

    for trait in possible_traits:
        trait_combinations = []
        for combo in combinations:
            new_combo = list(combo)
            new_combo.append(trait)
            trait_combinations.append(tuple(new_combo))

        new_combinations += _build_trait_combinations(
            trait_combinations, possible_traits - set([trait]), num_missing_traits - 1
        )

    return new_combinations


def get_crew_for_traits(crew: list[Crewmember], traits: Traits) -> list[Crewmember]:
    return [crewmember for crewmember in crew if crewmember.has_traits(traits)]


def find_crew_by_traits(
    crew: list[Crewmember], known_traits: Traits, possible_traits: list[Traits]
) -> list[Roster]:
    possible_crew = get_crew_for_traits(crew, known_traits)

    crew_by_traits = {
        t: Roster(get_crew_for_traits(possible_crew, t)) for t in possible_traits
    }

    return crew_by_traits


def find_crew_for_node(
    crew: list[Crewmember], node: Node
) -> Node:
    possible_traits = [trait for trait in traits if trait not in node.traits]

    trait_combinations = find_trait_combinations(
        possible_traits, node.traits.num_unknown_traits
    )

    crew_rosters = find_crew_by_traits(crew, node.traits, trait_combinations)

    updated_node = deepcopy(node)
    updated_node.rosters = crew_rosters

    return updated_node


def build_crew_occurrences(
    nodes: dict[str, Node]
) -> dict[Crewmember, list[Occurrence]]:
    occurrences = {}

    for node in nodes:
        for traits, roster in node.rosters.items():
            for crewmember in roster:
                occurrence = Occurrence(node.name, crewmember, traits)

                if not crewmember in occurrences:
                    occurrences[crewmember] = []

                occurrences[crewmember].append(occurrence)

    return occurrences


parser = argparse.ArgumentParser(
    prog="match_crew",
    description="Matches crew for battles",
)
parser.add_argument("-f", "--filename", action="store", default="crew.json")
parser.add_argument(
    "-l", "--level", action="store", type=int, default=5, choices=[1, 2, 3, 4, 5]
)
parser.add_argument(
    "-1",
    "--one",
    action="store",
    help="Traits for crew member 1 (; separated list)",
    default="",
)
parser.add_argument(
    "-2",
    "--two",
    action="store",
    help="Traits for crew member 2 (; separated list)",
    default="",
)
parser.add_argument(
    "-3",
    "--three",
    action="store",
    help="Traits for crew member 3 (; separated list)",
    default="",
)
parser.add_argument(
    "-4",
    "--four",
    action="store",
    help="Traits for crew member 4 (; separated list)",
    default="",
)
parser.add_argument(
    "-5",
    "--five",
    action="store",
    help="Traits for crew member 5 (; separated list)",
    default="",
)
parser.add_argument(
    "-t",
    "--traits",
    action="store",
    required=True,
    help="Possible traits (; separated list)",
)
parser.add_argument(
    "-e",
    "--exclude",
    action="store",
    help="Crewmembers to exclude (; separated list)",
    default="",
)
parser.add_argument(
    "-o",
    "--oneline",
    "--one-line",
    action=argparse.BooleanOptionalAction,
    help="Output entries on one line",
    type=bool,
    default=False,
)
parser.add_argument(
    "--keepsingletons",
    "--keep-singletons",
    action=argparse.BooleanOptionalAction,
    help="Keep rosters that contain just a single entry",
    type=bool,
    default=False,
)
args = vars(parser.parse_args())

node_names = ["one", "two", "three", "four", "five"]

with open(args["filename"], "r", encoding="utf-8") as f:
    all_crew = [Crewmember(crewmember) for crewmember in json.load(f)]

valid_traits = Traits(itertools.chain(*[
    crewmember.traits for crewmember in all_crew
]))

traits = Traits(parse_csv_string(args["traits"]))

invalid_traits = Traits([
    trait for trait in traits if trait and trait not in valid_traits
])

if invalid_traits:
    print(f"The following traits are invalid: {invalid_traits}", file=sys.stderr)
    exit(-1)


chain_nodes = [
    Node(
        name,
        Traits(parse_csv_string(args.get(name, ""))),
    ) for name in node_names
]

exclusions = set(
    crewmember.strip()
    for crewmember in parse_csv_string(args.get("exclude", ""))
)

crew = filter_crew_for_level(args["level"], all_crew)

nodes_with_rosters = [
    find_crew_for_node(crew, node)
    for node in chain_nodes
    if node
]

filter_list = []

if exclusions:
    filter_list.append(filter_exclusions_from_node)

if args.get('keepsingletons'):
    filter_list.append(filter_empty_from_node)
else:
    filter_list.append(filter_singletons_from_node)

filtered_nodes = filter_nodes(nodes_with_rosters, filter_list)

for node in filtered_nodes:
    print(f"\nSlot {node.name}\n============")

    sep = "" if args["oneline"] else "\n "

    for (t, m) in node.rosters.items():
        print(f"{t} ({len(m)}):{sep} {m}")

crew_occurrences = build_crew_occurrences(filtered_nodes)
repeated_occurrences = [
    occurrences for occurrences in crew_occurrences.values() if len(occurrences) > 1
]
repeated_occurrences.sort(
    key=lambda item: f"{len(item):4} {str(item[0].crewmember)}", reverse=True
)


print("\nRepeated Entries\n================")
for crew_occurrences in repeated_occurrences:
    instances = [
        f"{occurrence.slot} - {occurrence.traits}" for occurrence in crew_occurrences
    ]
    print(
        f"{crew_occurrences[0].crewmember} ({len(crew_occurrences)}): [ {'; '.join(instances)} ]"
    )

if len(repeated_occurrences) == 0:
    print("None")
