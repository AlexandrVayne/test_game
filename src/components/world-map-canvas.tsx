'use client'

/**
 * WorldMapCanvas — интерактивное превью карты мира Pockie Ninja.
 *
 * Эмулирует рендер-цикл будущей Pygame-версии:
 *   1. Фон (images/1.jpg из экспорта JPEXS)
 *   2. Платформы-кнопки (35 шт., DefineButton2_* / 1_up.png)
 *      — зоны, недоступные по уровню игрока, НЕактивны: обесцвечены,
 *        затемнены, помечены 🔒 и не реагируют на курсор
 *   3. Оверлей зданий и маркеров (DefineSprite_225, смещение 31:48)
 *      — маркеры ВСЕГДА фиолетовые (цвет не зависит от уровня игрока);
 *        на неактивных зонах — обесцвечены
 *   4. Пульсация фиолетовых маркеров; при наведении на локацию
 *      подсвечивается ТОЛЬКО её маркер (золотое ядро + ускоренный пульс)
 *   5. Debug-хитбоксы / hover-тултип
 *
 * Пиксель-перфект хиттест — альфа 4_hittest.png (аналог pygame.mask).
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Crosshair, Lock, MapPin, Sparkles, Tags } from 'lucide-react'

export interface Zone {
  id: number
  name: string
  x: number
  y: number
  w: number
  h: number
  village: boolean
  /** Диапазон уровней мобов зоны: 1–6, 6–11, 11–16, ... */
  level?: string
  /** Минимальный уровень игрока, при котором зона активна */
  unlockLevel?: number
  /** true в копии зоны, передаваемой наружу для неактивной зоны */
  locked?: boolean
}

export interface RouteMarker {
  x: number
  y: number
  r: number
  /** Зона (локация), за которой закреплён маркер — подсвечивается при её hover */
  zoneId?: number | null
}

export interface WorldMapConfig {
  map: {
    width: number
    height: number
    background: string
    overlay: { src: string; x: number; y: number }
  }
  zones: Zone[]
  routeMarkers: RouteMarker[]
}

export interface MapEvent {
  time: string
  text: string
  kind: 'click' | 'info'
}

interface Props {
  /** Уровень игрока: управляет активностью зон (цвет маркеров не меняет) */
  playerLevel: number
  onHoverZone: (zone: Zone | null, mapX: number, mapY: number) => void
  onZoneClick: (zone: Zone) => void
  selectedId: number | null
  onFps?: (fps: number) => void
  onActiveCount?: (active: number, total: number) => void
}

const IMG_BASE = '/worldmap'

/* ------------------------------------------------------------------ */
/* Цвет маркеров: ВСЕГДА фиолетовый (не зависит от уровня игрока).    */
/* Подсветка (золотое ядро + быстрый пульс) — только при наведении    */
/* на локацию и только у её собственного маркера.                     */
/* ------------------------------------------------------------------ */

/** Свечение пульсирующего маркера (фиолетовый, Tailwind fuchsia-500) */
const markerGlow = (a: number) => `rgba(217,70,239,${a})`

export default function WorldMapCanvas({
  playerLevel, onHoverZone, onZoneClick, selectedId, onFps, onActiveCount,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const configRef = useRef<WorldMapConfig | null>(null)
  const imagesRef = useRef<Record<string, HTMLImageElement>>({})
  // Пиксель-перфект маски (аналог pygame.mask.from_surface из 4_hittest.png)
  const masksRef = useRef<Record<number, { w: number; h: number; alpha: Uint8Array }>>({})
  const mouseRef = useRef<{ x: number; y: number; inside: boolean }>({ x: -1, y: -1, inside: false })
  const hoveredIdRef = useRef<number | null>(null)
  const selectedIdRef = useRef<number | null>(selectedId)
  // Оверлеи с обесцвеченными неактивными зонами: ключ — сигнатура неактивных зон
  const overlayCacheRef = useRef<Map<string, HTMLCanvasElement>>(new Map())
  // Обесцвеченные платформы неактивных зон: ключ — id зоны
  const desatCacheRef = useRef<Map<number, HTMLCanvasElement>>(new Map())
  // «Зона → её маркер» (индекс в cfg.routeMarkers): подсветка при hover
  const zoneMarkerRef = useRef<Map<number, number>>(new Map())
  // Копии зон с locked:true — стабильные ссылки (без ре-рендеров на каждый кадр)
  const lockedViewCacheRef = useRef<Map<number, Zone>>(new Map())
  // Последняя неактивная зона под курсором (для разового console.log)
  const prevLockedRef = useRef<number | null>(null)

  const [ready, setReady] = useState(false)
  const [showHitboxes, setShowHitboxes] = useState(false)
  const [showMarkers, setShowMarkers] = useState(true)
  // Названия деревень скрыты по умолчанию — вместо них тултип у курсора
  const [showLabels, setShowLabels] = useState(false)
  const [showOverlay, setShowOverlay] = useState(true)
  const [tooltipZone, setTooltipZone] = useState<Zone | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mouseCssRef = useRef({ x: 0, y: 0, w: 0, h: 0 })

  const showHitboxesRef = useRef(showHitboxes)
  const showMarkersRef = useRef(showMarkers)
  const showLabelsRef = useRef(showLabels)
  const showOverlayRef = useRef(showOverlay)
  const playerLevelRef = useRef(playerLevel)
  const activeCountCbRef = useRef(onActiveCount)
  const lastActiveCountRef = useRef(-1)

  useEffect(() => {
    showHitboxesRef.current = showHitboxes
    showMarkersRef.current = showMarkers
    showLabelsRef.current = showLabels
    showOverlayRef.current = showOverlay
  }, [showHitboxes, showMarkers, showLabels, showOverlay])

  useEffect(() => {
    selectedIdRef.current = selectedId
    playerLevelRef.current = playerLevel
    activeCountCbRef.current = onActiveCount
  }, [selectedId, playerLevel, onActiveCount])

  /** Загрузка config.json и всех спрайтов */
  useEffect(() => {
    let cancelled = false
    fetch(`${IMG_BASE}/config.json`)
      .then((r) => r.json())
      .then((cfg: WorldMapConfig) => {
        if (cancelled) return
        configRef.current = cfg
        // Закрепление «зона → маркер» из config.json (marker.zoneId)
        const zm: Map<number, number> = new Map()
        cfg.routeMarkers.forEach((m, i) => {
          if (m.zoneId != null && !zm.has(m.zoneId)) zm.set(m.zoneId, i)
        })
        zoneMarkerRef.current = zm
        const urls: string[] = [
          `${IMG_BASE}/${cfg.map.background}`,
          `${IMG_BASE}/${cfg.map.overlay.src}`,
        ]
        for (const z of cfg.zones) {
          urls.push(`${IMG_BASE}/buttons/b${z.id}_up.png`)
          urls.push(`${IMG_BASE}/buttons/b${z.id}_over.png`)
          urls.push(`${IMG_BASE}/buttons/b${z.id}_hit.png`)
        }
        let pending = urls.length
        const finish = () => {
          pending -= 1
          if (pending === 0 && !cancelled) {
            // Пиксель-перфект маски — аналог pygame.mask.from_surface(127)
            const masks: Record<number, { w: number; h: number; alpha: Uint8Array }> = {}
            for (const z of cfg.zones) {
              const hImg = imagesRef.current[`${IMG_BASE}/buttons/b${z.id}_hit.png`]
              if (!hImg || !hImg.complete || hImg.naturalWidth === 0) continue
              const c = document.createElement('canvas')
              c.width = hImg.naturalWidth
              c.height = hImg.naturalHeight
              const cctx = c.getContext('2d', { willReadFrequently: true })
              if (!cctx) continue
              cctx.drawImage(hImg, 0, 0)
              try {
                const data = cctx.getImageData(0, 0, c.width, c.height).data
                const alpha = new Uint8Array(c.width * c.height)
                for (let i = 0; i < alpha.length; i++) alpha[i] = data[i * 4 + 3]
                masks[z.id] = { w: c.width, h: c.height, alpha }
              } catch {
                // getImageData может упасть при CORS — остаётся прямоугольный хитбокс
              }
            }
            masksRef.current = masks
            setReady(true)
          }
        }
        for (const url of urls) {
          const img = new Image()
          img.onload = finish
          img.onerror = finish
          img.src = url
          imagesRef.current[url] = img
        }
      })
      .catch((e) => console.error('Ошибка загрузки config.json', e))
    return () => {
      cancelled = true
    }
  }, [])

  const getImg = useCallback((key: string): HTMLImageElement | null => {
    const img = imagesRef.current[key]
    return img && img.complete && img.naturalWidth > 0 ? img : null
  }, [])

  /** Зона активна для текущего уровня игрока? */
  const isActive = useCallback((z: Zone): boolean => {
    return (z.unlockLevel ?? 1) <= playerLevelRef.current
  }, [])

  /** Стабильная копия зоны с locked:true (для hover/клика/тултипа) */
  const lockedView = useCallback((z: Zone): Zone => {
    let v = lockedViewCacheRef.current.get(z.id)
    if (!v) {
      v = { ...z, locked: true }
      lockedViewCacheRef.current.set(z.id, v)
    }
    return v
  }, [])

  /** Обесцвеченная + затемнённая платформа для неактивной зоны (кэш по id) */
  const desaturatedPlatform = useCallback((z: Zone): HTMLCanvasElement | null => {
    const cached = desatCacheRef.current.get(z.id)
    if (cached) return cached
    const img = getImg(`${IMG_BASE}/buttons/b${z.id}_up.png`)
    if (!img) return null
    const c = document.createElement('canvas')
    c.width = img.naturalWidth
    c.height = img.naturalHeight
    const cctx = c.getContext('2d', { willReadFrequently: true })
    if (!cctx) return null
    cctx.drawImage(img, 0, 0)
    try {
      const im = cctx.getImageData(0, 0, c.width, c.height)
      const d = im.data
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] === 0) continue
        const gray = 0.3 * d[i] + 0.59 * d[i + 1] + 0.11 * d[i + 2]
        const v = gray * 0.5 + 8
        d[i] = v
        d[i + 1] = v
        d[i + 2] = v
      }
      cctx.putImageData(im, 0, 0)
      desatCacheRef.current.set(z.id, c)
      return c
    } catch {
      return null
    }
  }, [getImg])

  /**
   * Оверлей зданий и маркеров (маркеры остаются фиолетовыми — без
   * перекраски). Пиксели внутри прямоугольников НЕактивных зон
   * обесцвечиваются и затемняются. Кэш по сигнатуре неактивных зон.
   */
  const maskedOverlay = useCallback((inactiveSig: string): HTMLCanvasElement | null => {
    const cfg = configRef.current
    const src = getImg(`${IMG_BASE}/${cfg?.map.overlay.src ?? 'overlay.png'}`)
    if (!src || !cfg) return null
    const key = inactiveSig
    const cached = overlayCacheRef.current.get(key)
    if (cached) return cached
    const c = document.createElement('canvas')
    c.width = src.naturalWidth
    c.height = src.naturalHeight
    const ctx = c.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(src, 0, 0)
    try {
      const im = ctx.getImageData(0, 0, c.width, c.height)
      const d = im.data
      // Обесцвечивание области неактивных зон (здания + маркеры)
      if (inactiveSig) {
        const ox = cfg.map.overlay.x
        const oy = cfg.map.overlay.y
        for (const id of inactiveSig.split(',').map(Number)) {
          const z = cfg.zones.find((zz) => zz.id === id)
          if (!z) continue
          const x0 = Math.max(0, Math.round(z.x - z.w / 2 - ox))
          const y0 = Math.max(0, Math.round(z.y - z.h / 2 - oy))
          const x1 = Math.min(c.width, Math.round(z.x + z.w / 2 - ox))
          const y1 = Math.min(c.height, Math.round(z.y + z.h / 2 - oy))
          for (let y = y0; y < y1; y++) {
            for (let x = x0; x < x1; x++) {
              const i = (y * c.width + x) * 4
              if (d[i + 3] === 0) continue
              const gray = 0.3 * d[i] + 0.59 * d[i + 1] + 0.11 * d[i + 2]
              const v = gray * 0.5 + 8
              d[i] = v
              d[i + 1] = v
              d[i + 2] = v
            }
          }
        }
      }
      ctx.putImageData(im, 0, 0)
      overlayCacheRef.current.set(key, c)
      return c
    } catch {
      return null // CORS — рисуем оригинал
    }
  }, [getImg])

  /** Поиск зоны под курсором: пиксель-перфект, без фильтра активности.
   *  Возвращает зону + флаг «неактивна». */
  const hitTest = useCallback((mx: number, my: number): { zone: Zone; locked: boolean } | null => {
    const cfg = configRef.current
    if (!cfg) return null
    const HIT_THRESHOLD = 127
    let best: Zone | null = null
    for (const z of cfg.zones) {
      const hw = z.w / 2
      const hh = z.h / 2
      if (mx < z.x - hw || mx > z.x + hw || my < z.y - hh || my > z.y + hh) continue
      const mask = masksRef.current[z.id]
      if (mask) {
        const lx = Math.round(mx - (z.x - mask.w / 2))
        const ly = Math.round(my - (z.y - mask.h / 2))
        if (lx < 0 || ly < 0 || lx >= mask.w || ly >= mask.h) continue
        if (mask.alpha[ly * mask.w + lx] <= HIT_THRESHOLD) continue
      }
      if (!best || z.w * z.h < best.w * best.h) best = z
    }
    if (!best) return null
    return { zone: best, locked: !isActive(best) }
  }, [isActive])

  /** Главный рендер-цикл (аналог while running: pygame ...) */
  useEffect(() => {
    if (!ready) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const cfg = configRef.current!
    const W = cfg.map.width
    const H = cfg.map.height
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = W * dpr
    canvas.height = H * dpr

    let raf = 0
    let frames = 0
    let fpsTime = performance.now()

    const render = (t: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, W, H)

      const inactiveIds: number[] = []
      for (const z of cfg.zones) if (!isActive(z)) inactiveIds.push(z.id)
      const inactiveSig = inactiveIds.join(',')

      // --- Слой 1: фон ---
      const bg = getImg(`${IMG_BASE}/${cfg.map.background}`)
      if (bg) ctx.drawImage(bg, 0, 0, W, H)

      // --- Слой 2: платформы-кнопки (неактивные — обесцвеченные) ---
      for (const z of cfg.zones) {
        const active = isActive(z)
        const hovered = active && hoveredIdRef.current === z.id
        const selected = selectedIdRef.current === z.id
        if (active) {
          const key = `${IMG_BASE}/buttons/b${z.id}_${hovered || selected ? 'over' : 'up'}.png`
          const img = getImg(key)
          if (img) ctx.drawImage(img, z.x - z.w / 2, z.y - z.h / 2, z.w, z.h)
          if (selected) {
            ctx.save()
            ctx.strokeStyle = 'rgba(251, 191, 36, 0.95)'
            ctx.lineWidth = 2
            ctx.setLineDash([6, 4])
            ctx.strokeRect(z.x - z.w / 2 - 2, z.y - z.h / 2 - 2, z.w + 4, z.h + 4)
            ctx.restore()
          }
        } else {
          const img = desaturatedPlatform(z)
          if (img) ctx.drawImage(img, z.x - z.w / 2, z.y - z.h / 2, z.w, z.h)
        }
      }

      // --- Слой 3: оверлей зданий и маркеров (фиолетовые, без перекраски) ---
      if (showOverlayRef.current) {
        const ov = maskedOverlay(inactiveSig)
        if (ov) ctx.drawImage(ov, cfg.map.overlay.x, cfg.map.overlay.y)
      }

      // --- Слой 4: пульсация фиолетовых маркеров; hover локации — её маркер ---
      if (showMarkersRef.current) {
        const hz = hoveredIdRef.current != null
          ? cfg.zones.find((z) => z.id === hoveredIdRef.current)
          : null
        // Свечение остальных маркеров КОНСТАНТНО — при hover они не меняются
        const dimCol = markerGlow(0.45)
        for (let i = 0; i < cfg.routeMarkers.length; i++) {
          const m = cfg.routeMarkers[i]
          // Подсвечивается ТОЛЬКО маркер, закреплённый за зоной под курсором
          const isHi = hz != null && zoneMarkerRef.current.get(hz.id) === i
          if (isHi) {
            // Подсветка: яркое золотое ядро поверх точки + быстрый широкий пульс
            const pulse = 0.5 + 0.5 * Math.sin(t / 140 + i * 1.3)
            const r = m.r + 7 + pulse * 9
            const grad = ctx.createRadialGradient(m.x, m.y, 1, m.x, m.y, r + 5)
            grad.addColorStop(0, 'rgba(255,252,235,0.95)')
            grad.addColorStop(0.35, 'rgba(253,224,71,0.75)')
            grad.addColorStop(1, 'rgba(0,0,0,0)')
            ctx.fillStyle = grad
            ctx.beginPath()
            ctx.arc(m.x, m.y, r + 5, 0, Math.PI * 2)
            ctx.fill()
            const core = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, m.r * 1.25)
            core.addColorStop(0, 'rgba(255,254,245,1)')
            core.addColorStop(0.62, 'rgba(254,240,138,0.96)')
            core.addColorStop(1, 'rgba(253,224,71,0)')
            ctx.fillStyle = core
            ctx.beginPath()
            ctx.arc(m.x, m.y, m.r * 1.25, 0, Math.PI * 2)
            ctx.fill()
          } else {
            const pulse = 0.5 + 0.5 * Math.sin(t / 320 + i * 0.7)
            const r = m.r + 3 + pulse * 5
            const grad = ctx.createRadialGradient(m.x, m.y, 1, m.x, m.y, r + 4)
            grad.addColorStop(0, dimCol)
            grad.addColorStop(1, 'rgba(0,0,0,0)')
            ctx.fillStyle = grad
            ctx.beginPath()
            ctx.arc(m.x, m.y, r + 4, 0, Math.PI * 2)
            ctx.fill()
          }
        }
      }

      // --- Слой 5: 🔒-бейджи неактивных зон ---
      if (inactiveIds.length > 0) {
        ctx.save()
        ctx.font = '10px ui-sans-serif, system-ui, sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        for (const id of inactiveIds) {
          const z = cfg.zones.find((zz) => zz.id === id)!
          const bx = z.x
          const by = z.y + z.h / 2 - 11
          ctx.beginPath()
          ctx.arc(bx, by, 9, 0, Math.PI * 2)
          ctx.fillStyle = 'rgba(24,24,27,0.8)'
          ctx.fill()
          ctx.lineWidth = 1
          ctx.strokeStyle = 'rgba(161,161,170,0.65)'
          ctx.stroke()
          ctx.fillText('🔒', bx, by + 0.5)
        }
        ctx.restore()
      }

      // --- Слой 6: debug-хитбоксы ---
      if (showHitboxesRef.current) {
        for (const z of cfg.zones) {
          const active = isActive(z)
          const hovered = hoveredIdRef.current === z.id
          ctx.save()
          if (active) {
            ctx.strokeStyle = z.village
              ? hovered ? 'rgba(251,191,36,1)' : 'rgba(232,121,249,0.9)'
              : hovered ? 'rgba(251,191,36,1)' : 'rgba(74,222,128,0.65)'
            ctx.fillStyle = z.village ? 'rgba(232,121,249,0.10)' : 'rgba(74,222,128,0.06)'
          } else {
            ctx.strokeStyle = hovered ? 'rgba(251,191,36,0.9)' : 'rgba(113,113,122,0.6)'
            ctx.fillStyle = 'rgba(113,113,122,0.08)'
          }
          ctx.lineWidth = hovered ? 2 : 1
          ctx.strokeRect(z.x - z.w / 2, z.y - z.h / 2, z.w, z.h)
          ctx.fillRect(z.x - z.w / 2, z.y - z.h / 2, z.w, z.h)
          ctx.restore()
        }
      }

      // --- Слой 7: подписи деревень (по тумблеру) ---
      if (showLabelsRef.current) {
        ctx.save()
        ctx.font = '600 11px ui-sans-serif, system-ui, sans-serif'
        ctx.textAlign = 'center'
        for (const z of cfg.zones) {
          if (!z.village) continue
          const hovered = hoveredIdRef.current === z.id
          const label = z.name
          const tw = ctx.measureText(label).width
          const lx = z.x
          const ly = z.y + z.h / 2 + 14
          ctx.fillStyle = hovered ? 'rgba(251,191,36,0.95)' : 'rgba(0,0,0,0.55)'
          ctx.beginPath()
          ctx.roundRect(lx - tw / 2 - 6, ly - 10, tw + 12, 16, 8)
          ctx.fill()
          ctx.fillStyle = hovered ? '#1c1917' : '#faf5ff'
          ctx.fillText(label, lx, ly + 2)
        }
        ctx.restore()
      }

      // Отчёт об активных зонах (для бейджа в панели)
      const activeCount = cfg.zones.length - inactiveIds.length
      if (activeCount !== lastActiveCountRef.current) {
        lastActiveCountRef.current = activeCount
        activeCountCbRef.current?.(activeCount, cfg.zones.length)
      }

      // --- FPS ---
      frames += 1
      if (t - fpsTime >= 1000) {
        onFps?.(Math.round((frames * 1000) / (t - fpsTime)))
        frames = 0
        fpsTime = t
      }

      raf = requestAnimationFrame(render)
    }
    raf = requestAnimationFrame(render)
    return () => cancelAnimationFrame(raf)
  }, [ready, getImg, onFps, isActive, desaturatedPlatform, maskedOverlay])

  /** Координаты мыши в системе карты (0..768, 0..426) */
  const toMapCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const cfg = configRef.current
    const W = cfg?.map.width ?? 768
    const H = cfg?.map.height ?? 426
    return {
      x: ((e.clientX - rect.left) / rect.width) * W,
      y: ((e.clientY - rect.top) / rect.height) * H,
    }
  }

  /** Позиционирует тултип справа от курсора (с флипом у правого края).
   *  DOM мутация без ре-рендера — плавное следование за мышью. */
  const positionTooltip = useCallback(() => {
    const tip = tooltipRef.current
    if (!tip || !containerRef.current) return
    const { x, y, w, h } = mouseCssRef.current
    const cw = containerRef.current.clientWidth
    const tw = tip.offsetWidth
    const th = tip.offsetHeight
    let tx = x + 18
    if (tx + tw > cw - 6) tx = x - tw - 14
    let ty = y - th / 2
    ty = Math.max(6, Math.min(ty, h - th - 6))
    void w
    tip.style.transform = `translate3d(${Math.round(tx)}px, ${Math.round(ty)}px, 0)`
  }, [])

  // При монтировании/смене тултипа — сразу ставим его к последней позиции мыши
  useEffect(() => {
    if (tooltipZone) positionTooltip()
  }, [tooltipZone, positionTooltip])

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = toMapCoords(e)
    mouseRef.current = { x, y, inside: true }
    const hit = hitTest(x, y)
    const zone = hit?.zone ?? null
    const locked = hit?.locked ?? false
    const prev = hoveredIdRef.current
    // hover-подсветка платформы и маркеров — только для активных зон
    hoveredIdRef.current = zone && !locked ? zone.id : null
    e.currentTarget.style.cursor = zone ? (locked ? 'not-allowed' : 'pointer') : 'default'
    if (zone) onHoverZone(locked ? lockedView(zone) : zone, Math.round(x), Math.round(y))
    else if (prev !== null) onHoverZone(null, Math.round(x), Math.round(y))
    if ((zone ? zone.id : null) !== prev || locked) {
      setTooltipZone(zone ? (locked ? lockedView(zone) : zone) : null)
    }
    const rect = e.currentTarget.getBoundingClientRect()
    mouseCssRef.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      w: rect.width,
      h: rect.height,
    }
    if (zone) positionTooltip()
    if (prev !== hoveredIdRef.current && zone && !locked) {
      console.log(`[WorldMap] hover: ${zone.name} (DefineButton2_${zone.id}, Ур. ${zone.level ?? '?'})`)
    } else if (locked && prevLockedRef.current !== zone?.id) {
      console.log(`[WorldMap] неактивно: ${zone.name} — откроется на Ур. ${zone.unlockLevel}`)
    }
    prevLockedRef.current = locked ? zone?.id ?? null : null
  }

  const handleMouseLeave = () => {
    mouseRef.current = { x: -1, y: -1, inside: false }
    hoveredIdRef.current = null
    prevLockedRef.current = null
    setTooltipZone(null)
    onHoverZone(null, 0, 0)
  }

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = toMapCoords(e)
    const hit = hitTest(x, y)
    if (!hit) return
    const { zone, locked } = hit
    if (locked) {
      console.log(`[неактивно] ${zone.name} откроется на Ур. ${zone.unlockLevel}`)
      onZoneClick(lockedView(zone))
    } else {
      console.log(`Вы нажали на ${zone.name}`)
      onZoneClick(zone)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div ref={containerRef} className="relative overflow-hidden rounded-lg border border-zinc-700/60 bg-zinc-950 shadow-2xl">
        {/* Тултип у курсора: название + уровень (или 🔒 для неактивных) */}
        {tooltipZone && (
          <div
            ref={tooltipRef}
            className={`pointer-events-none absolute left-0 top-0 z-20 w-max rounded-lg border px-3 py-1.5 shadow-xl backdrop-blur-sm ${
              tooltipZone.locked
                ? 'border-zinc-600/80 bg-zinc-950/92 shadow-zinc-900/40'
                : tooltipZone.village
                  ? 'border-amber-500/70 bg-zinc-950/90 shadow-amber-900/30'
                  : 'border-zinc-600/70 bg-zinc-950/90'
            }`}
            style={{ willChange: 'transform' }}
          >
            <div className="flex items-center gap-1.5">
              {tooltipZone.locked ? (
                <Lock className="h-3.5 w-3.5 text-zinc-400" />
              ) : (
                tooltipZone.village && <Sparkles className="h-3.5 w-3.5 text-amber-400" />
              )}
              <span className="text-sm font-semibold leading-tight text-zinc-50">
                {tooltipZone.name}
              </span>
            </div>
            <div className={`mt-0.5 text-[11px] font-medium ${tooltipZone.locked ? 'text-zinc-400' : tooltipZone.village ? 'text-amber-300/90' : 'text-emerald-300/80'}`}>
              {tooltipZone.village ? 'Деревня' : 'Локация'} · Ур. {tooltipZone.level ?? '—'}
              {tooltipZone.locked && tooltipZone.unlockLevel != null &&
                ` · откроется на ${tooltipZone.unlockLevel} ур.`}
            </div>
          </div>
        )}
        {!ready && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/90">
            <div className="flex flex-col items-center gap-3 text-zinc-400">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-fuchsia-500 border-t-transparent" />
              <p className="text-sm">Загрузка ресурсов карты…</p>
            </div>
          </div>
        )}
        <canvas
          ref={canvasRef}
          className="block h-auto w-full select-none"
          style={{ aspectRatio: '768 / 426' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={handleClick}
          aria-label="Интерактивная карта мира Pockie Ninja"
        />
      </div>

      {/* Панель настроек отображения (аналог debug-флагов в Pygame) */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Switch id="sw-hit" checked={showHitboxes} onCheckedChange={setShowHitboxes} />
          <Label htmlFor="sw-hit" className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-300">
            <Crosshair className="h-3.5 w-3.5 text-emerald-400" /> Хитбоксы
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="sw-markers" checked={showMarkers} onCheckedChange={setShowMarkers} />
          <Label htmlFor="sw-markers" className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-300">
            <Sparkles className="h-3.5 w-3.5 text-fuchsia-400" /> Пульсация маркеров
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="sw-labels" checked={showLabels} onCheckedChange={setShowLabels} />
          <Label htmlFor="sw-labels" className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-300">
            <Tags className="h-3.5 w-3.5 text-amber-400" /> Названия деревень
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="sw-overlay" checked={showOverlay} onCheckedChange={setShowOverlay} />
          <Label htmlFor="sw-overlay" className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-300">
            <MapPin className="h-3.5 w-3.5 text-sky-400" /> Оверлей зданий
          </Label>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto h-7 border-amber-600/50 text-xs text-amber-400 hover:bg-amber-950/40 hover:text-amber-300"
          onClick={() => {
            setShowHitboxes(false)
            setShowMarkers(true)
            setShowLabels(false)
            setShowOverlay(true)
          }}
        >
          Сбросить вид
        </Button>
      </div>
    </div>
  )
}
