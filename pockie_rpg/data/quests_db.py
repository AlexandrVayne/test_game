"""Story quest data definitions (Layer A, data-driven).

Stage 172 — цепочка сюжетных квестов от Старейшины деревни (тексты и награды —
по заданию пользователя). Квесты выдаются строго по цепочке: следующий доступен
только после сдачи предыдущего. Цели: talk_to (поговорить с NPC — сдача
происходит тем же кликом по NPC), use_item (надеть предмет — goal_done
фиксируется в сейве, сдача у giver'а) и kill_mobs (Stage 173 — победить N
врагов; прогресс-счётчик story_quests_kill_progress в сейве, показывается
в трекере как «(2/3)»).
«Камни» наград исходного задания = золото (валюта игры).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StoryQuestDef:
    """Definition of a single story quest."""
    quest_id: str
    name: str
    giver_npc: str          # NpcDef.npc_id из npcs_db
    location: int           # MapLocation int — куда ведёт «Перейти» (цель)
    description: str        # лор-текст задания (окно предложения / трекер)
    goal_type: str          # "talk_to" | "use_item" | "kill_mobs"
    goal_target: str        # npc_id | item_id | префикс enemy_id ("samurai")
    goal_text: str          # строка «Прогресс» в трекере (без счётчика)
    goal_count: int = 1     # Stage 173 — сколько единиц цели (kill_mobs)
    reward_xp: int = 0
    reward_gold: int = 0
    reward_coupons: int = 0
    reward_item: str | None = None  # item_id из EQUIPMENT_DB (или None)
    offer_text: str = ""    # реплика giver'а при предложении квеста
    turn_in_text: str = ""  # реплика giver'а при сдаче
    reminder_text: str = "" # реплика giver'а, пока цель не выполнена


STORY_QUESTS: dict[str, StoryQuestDef] = {
    "quest_sakura_darkness": StoryQuestDef(
        quest_id="quest_sakura_darkness",
        name="Материк Сакура окутан тьмой",
        giver_npc="npc_elder",
        location=0,
        description=(
            "Материк Сакура окутан тьмой. Лишь самые могущественные "
            "ниндзя смогут выдержать это суровое испытание."
        ),
        goal_type="talk_to",
        goal_target="npc_elder",
        goal_text="Поговорите со Старейшиной деревни",
        reward_xp=5,
        reward_gold=5000,
        reward_coupons=10,
        reward_item="weapon_novice",
        offer_text=(
            "Материк Сакура окутан тьмой. Лишь самые могущественные "
            "ниндзя смогут выдержать это суровое испытание."
        ),
        turn_in_text=(
            "Добро пожаловать в деревню, я Старейшина деревни. Похоже, ты "
            "встретил Гаару по пути сюда. Он грозный ниндзя; если ты будешь "
            "тренироваться в этой деревне, возможно, ты достигнешь его силы."
        ),
        reminder_text="Поговори со мной, когда будешь готов начать обучение.",
    ),
    "quest_first_steps": StoryQuestDef(
        quest_id="quest_first_steps",
        name="Первые шаги",
        giver_npc="npc_elder",
        location=0,
        description="Используйте Оружие для новичка ур. 1.",
        goal_type="use_item",
        goal_target="weapon_novice",
        goal_text="Используйте Оружие для новичка ур. 1",
        reward_xp=5,
        reward_gold=0,
        reward_coupons=10,
        reward_item=None,
        offer_text=(
            "Теперь, когда ты получил своё первое оружие, "
            "давай продолжим путь."
        ),
        turn_in_text=(
            "Отлично! Оружие словно срослось с твоей рукой. "
            "Ты делаешь успехи, ученик."
        ),
        reminder_text=(
            "Открой инвентарь и надень Оружие для новичка ур. 1."
        ),
    ),
    "quest_report_progress": StoryQuestDef(
        quest_id="quest_report_progress",
        name="Доложите о своём прогрессе",
        giver_npc="npc_elder",
        location=0,
        description="Доложите Старейшине о своём прогрессе в обучении.",
        goal_type="talk_to",
        goal_target="npc_elder",
        goal_text="Поговорите со Старейшиной деревни",
        reward_xp=15,
        reward_gold=0,
        reward_coupons=10,
        reward_item=None,
        offer_text=(
            "Твои занятия не остались незамеченными. "
            "Доложи мне о своём прогрессе."
        ),
        turn_in_text="Пока хорошо. Давай продолжим твоё обучение.",
        reminder_text="Доложи мне о своём прогрессе, ученик.",
    ),
    # Stage 173 — продолжение цепочки: бой (по заданию пользователя —
    # «Победите N самураев», счётчик в трекере).
    "quest_defeat_samurai": StoryQuestDef(
        quest_id="quest_defeat_samurai",
        name="Победите самураев",
        giver_npc="npc_elder",
        location=1,  # Локация 1 — самураи (mob_1..mob_3)
        description=(
            "Самураи тревожат окрестности деревни. "
            "Победите 3 самураев на Локации 1."
        ),
        goal_type="kill_mobs",
        goal_target="samurai",  # любой враг, чей enemy_id начинается с этого
        goal_text="Победите самураев",
        goal_count=3,
        reward_xp=20,
        reward_gold=0,
        reward_coupons=10,
        reward_item=None,
        offer_text=(
            "Твоё оружие окрепло. Теперь покажи, чему научился: "
            "победи 3 самураев, что тревожат окрестности деревни."
        ),
        turn_in_text=(
            "Великолепно! Самураи повержены, деревня снова в безопасности. "
            "Ты делаешь успехи, ученик."
        ),
        reminder_text=(
            "Победи 3 самураев на Локации 1 — и возвращайся ко мне."
        ),
    ),
}

STORY_QUEST_CHAIN: tuple[str, ...] = (
    "quest_sakura_darkness",
    "quest_first_steps",
    "quest_report_progress",
    "quest_defeat_samurai",
)


def get_story_quest(quest_id: str) -> StoryQuestDef | None:
    """Return the story quest definition for ``quest_id``, or None."""
    return STORY_QUESTS.get(quest_id)


def chain_prerequisites_met(quest_id: str, completed: list[str]) -> bool:
    """True если все предыдущие квесты цепочки сданы (или квест первый)."""
    try:
        idx = STORY_QUEST_CHAIN.index(quest_id)
    except ValueError:
        return False
    return all(q in completed for q in STORY_QUEST_CHAIN[:idx])
