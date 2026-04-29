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
    def __init__(self, crew: list[Crewmember]):
        self.crew = crew

    def __contains__(self, item) -> bool:
        crewmembers = [item] if isinstance(item, str) else item

        try:
            for crewmember in crewmembers:
                if crewmember in self.crew:
                    return True
        except:
            pass

        return False

    def __bool__(self):
        return len(self.crew) > 0

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"{'; '.join([str(crewmember) for crewmember in self.crew])}"

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


def parse_csv_string(csv_data: str) -> str:
    if not csv_data:
        return []

    for row in csv.reader([csv_data], delimiter=";"):
        return row


def filter_crew_for_level(level: int, crew: list) -> list:
    return [crewmember for crewmember in crew if crewmember["max_rarity"] <= level]


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


def find_crew_for_slot(
    crew: list[Crewmember], slot_traits: Traits, exclusions: list[str] = []
):
    possible_traits = [trait for trait in traits if trait not in slot_traits]

    trait_combinations = find_trait_combinations(
        possible_traits, slot_traits.num_unknown_traits
    )

    crew_rosters = find_crew_by_traits(crew, slot_traits, trait_combinations)

    filtered = {t: m for (t, m) in crew_rosters.items() if m and not exclusions in m}

    return filtered


def build_crew_occurrences(
    crew_for_slots: dict[str, dict[Traits, list[Crewmember]]]
) -> dict[Crewmember, list[Occurrence]]:
    occurrences = {}

    for slot, rosters in crew_for_slots.items():
        for traits, roster in rosters.items():
            for crewmember in roster:
                occurrence = Occurrence(slot, crewmember, traits)

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
args = vars(parser.parse_args())

slot_list = ["one", "two", "three", "four", "five"]

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

crew_slots = {k: Traits(parse_csv_string(args.get(k, ""))) for k in slot_list}
exclusions = [
    crewmember.lower().strip()
    for crewmember in parse_csv_string(args.get("exclude", ""))
]

crew = filter_crew_for_level(args["level"], all_crew)

crew_for_slots = {
    slot: find_crew_for_slot(crew, crew_slots[slot], exclusions)
    for slot in slot_list
    if crew_slots[slot]
}

for (slot, crew_for_slot) in crew_for_slots.items():
    print(f"\nSlot {slot}\n============")

    sep = "" if args["oneline"] else "\n "

    for (t, m) in crew_for_slot.items():
        print(f"{t} ({len(m)}):{sep} {m}")

crew_occurrences = build_crew_occurrences(crew_for_slots)
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
        f"{crew_occurrences[0].crewmember} ({len(crew_occurrences)}): [{'; '.join(instances)} ]"
    )
