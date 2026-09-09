'use client'

/**
 * Витрина Pockie RPG (Ninja Wars 2) — ПРАВИЛО 4 из RULES.md.
 * Единственная страница: header → hero (скачать архив) → карточки версий → sticky footer.
 * Палитра: zinc (фоны), emerald (акценты), amber (кнопка/версия),
 * red (багфиксы), violet (фичи). indigo/blue ЗАПРЕЩЕНЫ.
 */

import {
  Bug,
  Download,
  Gamepad2,
  Scroll,
  Sparkles,
  Sword,
  Wrench,
} from 'lucide-react'

interface VersionCard {
  version: string
  date: string
  sizeMb?: number
  fixes?: string[]
  features?: string[]
  chores?: string[]
}

const VERSIONS: VersionCard[] = [
  {
    version: 'v203.0',
    date: 'Stage 205 — новый костюм «Сакура» (cloth14) со своими анимациями боя: наденьте костюм — и персонаж в бою превращается в девушку с полным набором анимаций. Первый переключаемый скин игрока',
    sizeMb: 13.0,
    features: [
      'КОСТЮМ С АНИМАЦИЯМИ — 5 анимаций (стойка 8 кадров, удар 11, бег 4, получение урона 7, смерть 2) извлечены из оригинальных SWF без потери качества: прозрачный фон, кадры в единых баундах, фирменные паузы таймлайна сохранены',
      'ЗЕРКАЛИРОВАНИЕ ПОД ИГРОКА — исходные анимации смотрели влево; все кадры аккуратно отражены по горизонтали попиксельно (без ресемпла), костюм смотрит вправо без рантайм-флипа',
      'МЕХАНИЗМ СКИНОВ — надетый костюм с полем motion_skin полностью меняет набор анимаций бойца (стойка/удар/бег/урон/смерть) во всех режимах боя: обычный, башня, гантлей, F9; снял костюм — снова Ичиго',
      'DATA-DRIVEN — будущие костюмы-скины добавляются папкой кадров + записью в базе костюмов, без изменений кода',
      'КОСТЮМ В ИГРЕ — «Костюм «Сакура»» (ловкостный архетип) лежит в стартовом инвентаре (2 шт: носить + синтез), работает и с заточенными инстансами',
    ],
    chores: [
      'Проверено: новый diag_stage205 59/59 (кадры, конфиг, скин-механизм, инстансы синтеза, F9, фриз смерти), полный регресс 13/13 + 18/18 + 10/10 + все diag, визуальный скриншот-контроль боя',
      'Аватарки HUD для костюма пока от Ичиго — будут заменены, когда придут оригинальные',
    ],
  },
  {
    version: 'v202.2',
    date: 'Stage 204 — волна чистки по AST-аудиту: удалено ~440 строк мёртвого кода, топовые дубли консолидированы. Проект похудел на 695 строк без изменений поведения',
    sizeMb: 13.0,
    chores: [
      'МЁРТВЫЙ КОД — ~70 устаревших констант в config.py (fullscreen-легаси, громкости звука, старые параметры навыков/башни/мирового босса, дубли HUD-цветов) и ~30 функций/методов в 13 файлах удалены после верификации «ноль вызовов» по всему проекту',
      'ЭФФЕКТЫ БОЯ — четыре класса оверлеев переведены на иерархию с базовыми классами циклической и одноразовой анимации: лед/щит/туча/яд и файрбол больше не дублируют одинаковый код покадрового обновления',
      'ЕДИНЫЙ СБРОС БОЯ — шесть расходившихся копий сброса боевого состояния сведены в один метод с параметром «с отсчётом 3-2-1 или без»; входы/выходы боя, гантлей и F9-режим используют общую точку',
      'ФАБРИКА ВРАГА — создание вражеского бойца с аниматором вынесено в один хелпер (было 3 копии); попутно исправлен латентный баг F9-режима: несуществующая папка анимации и потерянный тип врага',
      'ПУТИ И ИКОНКИ — трёхкратный dirname×4-хак путей иконок заменён на константу ассетов; дефолтные иконки/слоты лута вынесены в базу предметов вместо двух одинаковых словарей',
      'Проверено: py_compile всех 40 файлов, ruff, полный импорт-смоук; verify_stage202 13/13, регресс Stage 201 18/18, автотест боя 10/10, все diag-диагностики и Hi-DPI smoke, headless-прогоны входа/выхода боя и F9',
    ],
  },
  {
    version: 'v202.1',
    date: 'Stage 203 — рефакторинг UI по чек-листу: удалены дубли кода и мёртвые ветки, единая полоска HP/MP для карты и боя, общий визуал Х-кнопок, тема цветов UI',
    sizeMb: 13.2,
    features: [
      'ТЕМА ЦВЕТОВ UI — в config появился UI_THEME: семантические имена (gold, zinc-800, red-600…) вместо сырых RGB-троек; новый и трогаемый код уже на теме, старый мигрируется постепенно',
    ],
    chores: [
      'ТУЛТИП БАФОВ — тултип иконок бафов на карте переведён на общий хелпер «панель у курсора» (третий потребитель после статусов и лута): одинаковая панель, рамка, перенос, флип и кламп; −40 строк дублированного кода',
      'ЕДИНАЯ ПОЛОСКА — _render_map_bar удалена: HP/MP/EXP на карте рисуются общим _render_bar в упрощённом режиме (simple=True) с точным сохранением вида; −45 строк дубля',
      'ИКОНКИ ЛУТА — два дублирующих кэша иконок удалены (−52 строки): всё через _su_image с новым режимом fit (вписывание с сохранением пропорций — важно для неквадратных иконок), убран dirname×4-хак пути',
      'МЁРТВЫЙ КОД — в endgame-экране удалены всегда-истинные проверки hasattr и 55-строчный запасной рендер лута, который никогда не выполнялся',
      'Х-КНОПКИ — единый визуал красного квадрата с × для всех окон и модалок (общий хелпер, цвета в UI_THEME)',
      'Проверено: verify_stage202 13/13, регресс Stage 201 18/18, автотест боя 10/10, все diag-диагностики кликов/drag/фона/smoke, py_compile/ruff',
    ],
  },
  {
    version: 'v202.0',
    date: 'Stage 202 — фиксы боя: числа урона больше не «плавают», подложка уровня врага покрывает текст целиком; единый хелпер тултипов; плавное появление окна боя',
    sizeMb: 13.2,
    fixes: [
      'ЧИСЛА УРОНА — найден и исправлен баг с перезаписью масштаба рендера пульс-фактором вспышки: позиции цифр перестали скакать и «плавать» при появлении новых чисел (особенно заметно было на 2К)',
      'ПОДЛОЖКА УРОВНЯ ВРАГА — плашка под «Ур. N» теперь считается по ширине текста с аутлайном: чёрный контур уровня больше не вылезает за левый край подложки',
    ],
    features: [
      'ПЛАВНОЕ ПОЯВЛЕНИЕ БОЯ — окно боя (вместе с рамкой и затемнением фона) проявляется за 0.15 секунды при входе в бой, как модалки инвентаря/кузницы',
      'ЕДИНЫЙ ТУЛТИП — тултип статуса и лут-тултип работают через один хелпер «панель у курсора»: одинаковые паддинги, рамки, перенос текста и флип у краёв экрана',
    ],
    chores: [
      'РЕФАКТОРИНГ — _render_hud (~350 строк) разбита на симметричные половины игрока/врага + ряды иконок статусов и очередь гантлея отдельными методами',
      'Проверено: verify_stage202.py 13/13 (порядконезависимость чисел урона, геометрия подложки по реальным blit\'ам, флипы/клампы тултипов, восстановление альфы кэшей), регресс Stage 201 18/18, все diag-диагностики, py_compile/ruff',
    ],
  },
  {
    version: 'v201.0',
    date: 'Stage 201 — бой мигрирован на нативный Hi-DPI: окно боя рендерится в физических пикселях монитора, текст и полоски чёткие, layout не изменился',
    sizeMb: 13.2,
    features: [
      'ЧЁТКИЙ БОЙ — окно боя больше не растягивается из буфера 1280×720: весь контент (текст, полоски HP/MP, иконки статусов, лог, кнопки) рисуется в native-разрешении окна (на 2К — 1536×864, масштаб 1.2), композит без ресемпла',
      'СПРАЙТЫ И ЭФФЕКТЫ — бойцы, ледяной блок, купол, туча, яд, фаербол и частицы рендерятся в нативных размерах (кэши по размеру — без просадки FPS)',
      'ФОН БОЯ — масштаб снимка локации кэшируется и обновляется 4 раза/сек вместе со снимком (раньше full-screen ресемпл был каждый кадр, ~6мс)',
      'ПОСЛЕДНИЙ LEGACY-ЭКРАН — карта, инвентарь, кузница, магазин, синтез, гардероб, звания и теперь бой рендерятся нативно; арена и тест-бой (F9) остаются legacy (dev-режим)',
    ],
    chores: [
      'Проверено: verify_battle_native.py 18/18 (scale 1.2, окно 1536×864, клики-ховеры в дизайн-пространстве, композит 1:1, endgame, legacy-путь), автотест боя 10/10, весь регресс кликов/drag/фона/smoke, py_compile/ruff, бенчмарк 9.06 vs 8.97 мс/кадр (паритет)',
    ],
  },
  {
    version: 'v200.0',
    date: 'Stage 200 — имя и уровень центрированы в подложке, текст ярче, подложка плавно проявляется при входе в бой, цвета HUD собраны в тему',
    features: [
      'ЦЕНТРИРОВАНИЕ — имя и уровень теперь на одной средней линии подложки (уровень больше не «висит» ниже базовой линии имени)',
      'ЯРЧЕ ТЕКСТ — имя стало чисто-белым, уровень — ярко-жёлтым (yellow-300), плюс лёгкая рамка по краю подложки: читаемость заметно выросла на любых локациях',
      'ПЛАВНОЕ ПОЯВЛЕНИЕ — подложка имени/уровня проявляется за 0.4 секунды вместе с входом в бой (раньше появлялась резко)',
      'HUD_THEME — все цвета HUD-текста/подложек/рамок собраны в один словарь в config: смена стиля HUD теперь правкой одного блока',
    ],
    chores: [
      'Проверено: пиксельные тесты (центры текста на средней линии ±3px, белое имя, yellow-300 уровень, рамка zinc-500, fade 0→0.5→1.0), весь регресс 193-199, автотест боя 10/10, py_compile/ruff',
    ],
  },
]

function Bullet({ kind, text }: { kind: 'fix' | 'feat' | 'chore'; text: string }) {
  const Icon = kind === 'fix' ? Bug : kind === 'feat' ? Sparkles : Wrench
  const cls =
    kind === 'fix'
      ? 'text-red-400'
      : kind === 'feat'
        ? 'text-violet-400'
        : 'text-zinc-400'
  return (
    <li className="flex items-start gap-2 text-sm leading-snug text-zinc-300">
      <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${cls}`} aria-hidden />
      <span>{text}</span>
    </li>
  )
}

export default function Home() {
  const latest = VERSIONS[0]
  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-600 to-zinc-800 shadow-lg shadow-emerald-950/50">
              <Gamepad2 className="h-5 w-5 text-emerald-100" aria-hidden />
            </div>
            <div>
              <h1 className="text-base font-bold leading-tight sm:text-lg">
                Pockie RPG (Ninja Wars 2)
              </h1>
              <p className="text-xs text-zinc-400">
                Single-player 2D пошаговая RPG · Python + pygame-ce
              </p>
            </div>
          </div>
          <span className="ml-auto rounded-md border border-amber-600/60 bg-amber-950/40 px-2.5 py-1 text-sm font-bold text-amber-300">
            {latest.version}
          </span>
        </div>
      </header>

      {/* Main */}
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6">
        {/* Hero */}
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-center sm:p-10">
          <Sword className="mx-auto mb-4 h-10 w-10 text-emerald-400" aria-hidden />
          <h2 className="text-xl font-bold sm:text-2xl">
            Скачать последнюю версию
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-zinc-400">
            Полный архив проекта: исходники <code className="text-zinc-300">src/pockie_rpg/</code>,
            ассеты, шрифт и документация. Распаковать → <code className="text-zinc-300">python -m pockie_rpg.main</code>.
          </p>
          <a
            href={`/pockie_rpg_${latest.version}.zip`}
            download
            className="mt-6 inline-flex min-h-[52px] items-center gap-2.5 rounded-xl bg-amber-500 px-7 py-3.5 text-base font-bold text-zinc-950 shadow-lg shadow-amber-950/40 transition-all hover:scale-[1.02] hover:bg-amber-400 active:scale-[0.99]"
          >
            <Download className="h-5 w-5" aria-hidden />
            Скачать pockie_rpg_{latest.version}.zip ({latest.sizeMb ?? 10.6} МБ)
          </a>
          <p className="mt-4 text-xs text-zinc-500">
            Windows: <code className="text-zinc-400">python -m venv .venv → pip install -e . → python -m pockie_rpg.main</code>
          </p>
        </section>

        {/* Version cards */}
        <section aria-label="История версий" className="mt-8">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            <Scroll className="h-4 w-4 text-emerald-400" aria-hidden />
            Что нового
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {VERSIONS.map((v) => (
              <article
                key={v.version}
                className="flex flex-col gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-amber-600/60 bg-amber-950/40 px-2 py-0.5 text-sm font-bold text-amber-300">
                    {v.version}
                  </span>
                  <span className="text-xs text-zinc-500">{v.date}</span>
                </div>
                {v.fixes && v.fixes.length > 0 && (
                  <div>
                    <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-red-400">
                      Багфиксы
                    </h3>
                    <ul className="space-y-1.5">
                      {v.fixes.map((f) => (
                        <Bullet key={f} kind="fix" text={f} />
                      ))}
                    </ul>
                  </div>
                )}
                {v.features && v.features.length > 0 && (
                  <div>
                    <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-violet-400">
                      Новое
                    </h3>
                    <ul className="space-y-1.5">
                      {v.features.map((f) => (
                        <Bullet key={f} kind="feat" text={f} />
                      ))}
                    </ul>
                  </div>
                )}
                {v.chores && v.chores.length > 0 && (
                  <div>
                    <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Рефакторинг
                    </h3>
                    <ul className="space-y-1.5">
                      {v.chores.map((c) => (
                        <Bullet key={c} kind="chore" text={c} />
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      </main>

      {/* Footer sticky */}
      <footer className="mt-auto border-t border-zinc-800 bg-zinc-900/50 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-6">
          <p className="text-xs text-zinc-500">
            Pockie RPG (Ninja Wars 2) · клон Pockie Ninja на Python + pygame-ce · без БД и веба
          </p>
          <p className="text-xs text-zinc-600">
            config → data → combat → game → ui
          </p>
        </div>
      </footer>
    </div>
  )
}
