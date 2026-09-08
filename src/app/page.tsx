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
  {
    version: 'v199.0',
    date: 'Stage 199 — тёмная подложка под именем и уровнем бойцов над полосками HP/MP',
    features: [
      'ПОДЛОЖКА ИМЁН — под именем и уровнем бойца (над полосками HP/MP) появилась слабозаметная тёмная плашка: имена читаются на любых локациях, включая светлые',
      'Подложка общая для имени и уровня, со скруглением, зеркально у обоих бойцов; размеры точные — ничего не вылезает за плашку',
    ],
    chores: [
      'Проверено: пиксельные тесты (подложка в зонах имени/уровня у обоих, чистый фон выше, подложка не заходит на полоски, текст рисуется поверх), весь регресс 193-198, автотест боя 10/10, py_compile/ruff',
    ],
  },
  {
    version: 'v198.0',
    date: 'Stage 198 — световой блик пробегает по полоскам HP/MP раз в 3 секунды, тень под городскими плашками, «подъём» тени карточек при hover',
    features: [
      'SHINE SWEEP — раз в 3 секунды по заливке HP/MP пробегает мягкий световой блик (слева направо у Ичиго, зеркально у врага): полоски выглядят как живое стекло',
      'ПОДЪЁМ КАРТОЧЕК — при наведении на карточку моба тень под ней углубляется и смещается: карточка «приподнимается» над картой',
    ],
    fixes: [
      'Тень под городскими плашками (Арена/Магазин/Башня) — единый механизм теней',
      'Текст уровня («Ур. N») получил 1px чёрный аутлайн — читается на светлых фонах',
      'Удалён дубль теневого кода: все тени игры теперь через один хелпер',
    ],
    chores: [
      'Проверено: дельта-профили sweep (пик бэенда движется 256→488 у Ичиго и 1024→790 у врага), тень/подъём карточек через настоящий рендер карты, весь регресс 193-197, автотест боя 10/10, py_compile/ruff',
    ],
  },
  {
    version: 'v197.0',
    date: 'Stage 197 — тени под карточками мобов и именами бойцов, стеклянный блик полосок, единый хелпер теней',
    features: [
      'ТЕНИ ПОД КАРТОЧКАМИ МОБОВ — карточки врагов на карте получили мягкую тень (как полоски HP/MP в бою): HUD карты стал объёмнее, карточки читаются как «плашки» над локацией',
      'АУТЛАЙН ИМЁН — имена бойцов над полосками обведены 1px чёрным контуром: читаемость на светлых фонах локаций',
      'СТЕКЛЯННЫЙ БЛИК — 1px светлая линия вдоль верхнего края полосок HP/MP в паре с тенью: полоски выглядят как стеклянные',
    ],
    chores: [
      'РЕФАКТОРИНГ — все тени игры (плашечные и силуэтные) собраны в единый хелпер _drop_shadow: полоски, иконки статусов, карточки мобов — один механизм с кэшем, вместо трёх копий',
      'Проверено: пиксельные тесты (силуэтный/плашечный режимы, аутлайн, блик, тень карточки через настоящий рендер карты), весь предыдущий регресс 193-196, автотест боя 10/10, py_compile/ruff',
    ],
  },
  {
    version: 'v196.0',
    date: 'Stage 196 — мягкая тень под полосками HP/MP (глубина над фоном локации)',
    features: [
      'DROP-SHADOW ПОЛОСОК — под HP и MP (у обоих бойцов) появилась мягкая тень: тёмная плашка 2px + полупрозрачный ореол, полоски больше не «приклеены» к фону локации, HUD стал объёмным',
      'Тень рисуется один раз и кэшируется — производительность не изменилась; видна только с нижнего правого края (свет сверху-слева), тело полосок не тронуто',
    ],
    chores: [
      'Проверено: пиксельные тесты (тень со всех открытых краёв всех 4 полосок, ореол светлее ядра, отсутствие тени внутри полосок, конечность тени), автотест боя 10/10, py_compile/ruff',
    ],
  },
  {
    version: 'v195.0',
    date: 'Stage 195 — HP/MP списываются зеркально к центру, MP уже HP, иконки статусов: тень, счётчик ходов, тултип при наведении',
    features: [
      'ЗЕРКАЛЬНОЕ СПИСАНИЕ — у Ичиго полоска уменьшается слева направо, у врагов — справа налево к центру: «свежие» HP всегда у золотого ромба VS, урон «съедает» полоску с внешних краёв',
      'ТУЛТИПЫ СТАТУСОВ — наведение на иконку эффекта (лёд, яд, туча, щит…) показывает панель: название, описание механики и сколько ходов осталось',
      'СЧЁТЧИКИ ХОДОВ — на иконках с длительностью больше хода висит мини-цифра (лёд: 2, яд: 4) — таймеры эффектов видны без наведения',
      'ГРАДИЕНТ MP — синяя полоска маны переливается к голубому кончику у центра, зеркально HP',
    ],
    fixes: [
      'MP-полоска стала немного уже HP-полоски, их кончики (у центра) совпадают по вертикали',
      'Под иконками статусов — мягкая тень 2px: эффекты больше не сливаются с фоном локации',
    ],
    chores: [
      'Проверено: пиксельные тесты (направление списания обеих сторон, совпадение кончиков MP/HP, цвета градиентов, тень, бейджи, панель тултипа у курсора), автотест боя 10/10, py_compile/ruff',
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
