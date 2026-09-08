"""NPC data definitions (Layer A, data-driven).

Stage 172 — сюжетные NPC на локациях карты: Жаба (Локация 1, без квестов)
и Старейшина деревни (CITY, giver цепочки сюжетных квестов — quests_db).
Аватарки: assets/npcs/. Спрайт-анимация жабы: assets/extracted/npc_toad_idle/
(SWF n26005.s12755.swf → 17 кадров idle; Stage 176: ре-экстракция полных
шейпов-поз — плашка «Toad Sovereign» и запечённая тень удалены, голова в
кадре прыжка больше не обрезается; кадр 121×168, кроп y=62 не используется).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NpcDef:
    """Definition of a map NPC."""
    npc_id: str
    name: str
    title: str
    location: int            # MapLocation int (0=CITY, 1=LOC1, ...)
    avatar_filename: str     # file under assets/npcs/ (portrait + dialog)
    idle_folder: str | None  # assets/extracted/<folder>/N.png idle animation
    idle_fps: float
    ground_x: int            # design-coords: точка ног на карте (1280×720)
    ground_y: int
    sprite_h: int            # высота спрайта на карте (дизайн-пиксели)
    hover_text: str
    flavor: tuple[str, ...]  # реплики без квеста (клик по NPC)
    # Stage 174 — текстовая метка вместо спрайта: на карте рисуется кликабельная
    # плашка map_text в (label_x, label_y) (центр), аватар ТОЛЬКО внутри диалога.
    map_text: str | None = None
    label_x: int = 640
    label_y: int = 560


NPCS: dict[str, NpcDef] = {
    "npc_toad": NpcDef(
        npc_id="npc_toad",
        name="Жаба",
        title="Загадочный обитатель Локации 1",
        location=1,
        avatar_filename="toad_avatar.png",
        idle_folder="npc_toad_idle",
        idle_fps=8.0,
        ground_x=170,
        ground_y=628,
        sprite_h=154,  # кадр 168px × (150/164) — визуальный размер жабы как в Stage 172
        hover_text="Ква-а-а…",
        flavor=(
            "Ква. Жаба смотрит на тебя с неожиданным достоинством.",
            "Похоже, эта жаба повидала больше битв, чем иные ниндзя.",
            "Жаба невозмутима. В её глазах — тьма Материка Сакура.",
        ),
    ),
    "npc_elder": NpcDef(
        npc_id="npc_elder",
        name="Старейшина деревни",
        title="Хранитель деревни",
        location=0,
        avatar_filename="elder_avatar.png",
        idle_folder=None,
        idle_fps=0.0,
        ground_x=920,  # не используется (map_text) — оставлен для совместимости
        ground_y=628,
        sprite_h=200,
        hover_text="Подойди, ученик.",
        flavor=(
            "Ты проделал долгий путь, ученик. Деревня гордится тобой.",
            "Тренируйся усердно — однажды ты превзойдёшь даже Гаару.",
            "Тьма отступает, пока такие, как ты, стоят на страже.",
        ),
        # Stage 174 — на карте только кликабельный текст по центру под
        # карточками города; спрайт/аватар на карте убраны (аватар — в окне).
        map_text="Старейшина деревни",
        label_x=640,
        label_y=560,
    ),
}

NPC_QUEST_GIVERS: tuple[str, ...] = ("npc_elder",)


def get_npc(npc_id: str) -> NpcDef | None:
    """Return the NPC definition for ``npc_id``, or None."""
    return NPCS.get(npc_id)


def npcs_at_location(location: int) -> list[NpcDef]:
    """All NPCs standing at the given map location (stable order)."""
    return [n for n in NPCS.values() if n.location == location]
