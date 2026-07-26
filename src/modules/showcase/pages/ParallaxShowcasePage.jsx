import { useState, useEffect, useRef, useCallback } from 'react'
import styles from './ParallaxShowcasePage.module.css'

const clamp = (v, min, max) => Math.min(Math.max(v, min), max)
const lerp = (a, b, t) => a + (b - a) * t

function progress(scrollY, start, end) {
  return clamp((scrollY - start) / (end - start), 0, 1)
}

export default function ParallaxShowcasePage() {
  const containerRef = useRef(null)
  const [scrollY, setScrollY] = useState(0)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [vh, setVh] = useState(800)
  const animFrameRef = useRef(null)

  const handleScroll = useCallback(() => {
    if (animFrameRef.current) return
    animFrameRef.current = requestAnimationFrame(() => {
      const el = containerRef.current
      if (el) setScrollY(el.scrollTop)
      animFrameRef.current = null
    })
  }, [])

  const handleMouseMove = useCallback((e) => {
    const el = containerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    setMousePos({
      x: ((e.clientX - rect.left) / rect.width - 0.5) * 2,
      y: ((e.clientY - rect.top) / rect.height - 0.5) * 2
    })
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    setVh(el.clientHeight)
    const onResize = () => setVh(el.clientHeight)
    window.addEventListener('resize', onResize)
    el.addEventListener('scroll', handleScroll, { passive: true })
    el.addEventListener('mousemove', handleMouseMove, { passive: true })
    return () => {
      window.removeEventListener('resize', onResize)
      el.removeEventListener('scroll', handleScroll)
      el.removeEventListener('mousemove', handleMouseMove)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [handleScroll, handleMouseMove])

  /* ── Scroll-driven progress values ── */
  const heroP       = progress(scrollY, 0, vh)                       // 0→1 during hero
  const heroExit    = progress(scrollY, 0, vh * 1.2)                 // hero fade out
  const depthP      = progress(scrollY, vh * 0.8, vh * 1.8)          // depth section
  const cardsP      = progress(scrollY, vh * 1.8, vh * 2.8)          // cards section
  const constellP   = progress(scrollY, vh * 2.8, vh * 3.8)          // constellation section
  const waveP       = progress(scrollY, vh * 3.8, vh * 4.6)          // wave section

  /* ── Hero 3D: scroll drives rotation ── */
  const cubeRotY    = heroP * 360
  const cubeRotX    = lerp(-20, 25, heroP)
  const cubeScale   = lerp(1, 1.4, heroP)
  const torusRotZ   = heroP * 270
  const torusOffY   = lerp(0, -40, heroP)
  const octaRot     = heroP * 540
  const octaScale   = lerp(1, 0.6, heroP)
  const stageRotX   = mousePos.y * -6 + heroP * 15
  const stageRotY   = mousePos.x * 6 + heroP * -10
  const heroOpacity = 1 - heroExit
  const heroTransY  = scrollY * 0.35

  /* ── Orbs: scroll shifts position ── */
  const orb1Y = scrollY * 0.08 + heroP * 60
  const orb2Y = scrollY * -0.05 + heroP * -40
  const orb3Y = scrollY * 0.12 + depthP * 80
  const orb4Y = scrollY * -0.03 + cardsP * -30

  /* ── Depth cards: scroll stagger ── */
  const depthBase = vh * 1.2

  /* ── 3D Cards: scroll fan-out ── */
  const cardsBase = vh * 2.2

  return (
    <div className={styles.scrollContainer} ref={containerRef}>
      {/* ── Background orbs: scroll-reactive ── */}
      <div className={styles.bg3dScene}>
        <div className={styles.bgOrb} style={{
          '--orb-color': 'var(--parallax-coral)',
          '--orb-size': 'clamp(220px, 32vw, 520px)',
          '--orb-x': '12%', '--orb-y': '8%',
          transform: `translate(${mousePos.x * 30}px, ${orb1Y + mousePos.y * 30}px)`
        }} />
        <div className={styles.bgOrb} style={{
          '--orb-color': 'var(--parallax-amber)',
          '--orb-size': 'clamp(260px, 36vw, 600px)',
          '--orb-x': '68%', '--orb-y': '3%',
          transform: `translate(${mousePos.x * -20}px, ${orb2Y + mousePos.y * -20}px)`
        }} />
        <div className={styles.bgOrb} style={{
          '--orb-color': 'var(--parallax-rose)',
          '--orb-size': 'clamp(190px, 26vw, 460px)',
          '--orb-x': '48%', '--orb-y': '55%',
          transform: `translate(${mousePos.x * 25}px, ${orb3Y + mousePos.y * 15}px)`
        }} />
        <div className={styles.bgOrb} style={{
          '--orb-color': 'var(--parallax-sage)',
          '--orb-size': 'clamp(150px, 22vw, 380px)',
          '--orb-x': '82%', '--orb-y': '70%',
          transform: `translate(${mousePos.x * -15}px, ${orb4Y + mousePos.y * 25}px)`
        }} />
      </div>

      {/* ── Hero ── */}
      <section className={styles.hero} style={{ opacity: heroOpacity }}>
        <div className={styles.heroContent} style={{ transform: `translateY(${heroTransY}px)` }}>
          <div className={styles.hero3dStage}
            style={{ transform: `perspective(1200px) rotateX(${stageRotX}deg) rotateY(${stageRotY}deg)` }}
          >
            {/* Cube: rotates & scales with scroll */}
            <div className={styles.heroShape} data-shape="cube">
              <div className={styles.cube}
                style={{ transform: `rotateX(${cubeRotX}deg) rotateY(${cubeRotY}deg) scale(${cubeScale})` }}
              >
                <div className={`${styles.cubeFace} ${styles.cubeFront}`} />
                <div className={`${styles.cubeFace} ${styles.cubeBack}`} />
                <div className={`${styles.cubeFace} ${styles.cubeLeft}`} />
                <div className={`${styles.cubeFace} ${styles.cubeRight}`} />
                <div className={`${styles.cubeFace} ${styles.cubeTop}`} />
                <div className={`${styles.cubeFace} ${styles.cubeBottom}`} />
              </div>
            </div>
            {/* Torus: rotates & lifts with scroll */}
            <div className={styles.heroShape} data-shape="torus">
              <div className={styles.torus}
                style={{ transform: `translateY(${torusOffY}px) rotateX(60deg) rotateZ(${torusRotZ}deg)` }}
              />
            </div>
            {/* Octahedron: spins & shrinks with scroll */}
            <div className={styles.heroShape} data-shape="octahedron">
              <div className={styles.octahedron}
                style={{ transform: `rotate(${45 + octaRot}deg) scale(${octaScale})` }}
              />
            </div>
          </div>

          <h1 className={styles.heroTitle}>
            <span className={styles.titleLine}>Beyond</span>
            <span className={styles.titleLineAccent}>the Surface</span>
          </h1>
          <p className={styles.heroSub}>
            Scroll to explore — every shape responds to your movement
          </p>
          <div className={styles.scrollHint}>
            <div className={styles.scrollHintMouse}>
              <div className={styles.scrollHintWheel} />
            </div>
            <span>Scroll to explore</span>
          </div>
        </div>
      </section>

      {/* ── Section 1: Depth — 3D layers driven by scroll ── */}
      <section
        className={`${styles.parallaxSection} ${depthP > 0 ? styles.sectionVisible : ''}`}
        data-section="depth"
        style={{ opacity: depthP > 0 ? Math.min(depthP * 3, 1) : 0 }}
      >
        <div className={styles.sectionContent}>
          <div className={styles.sectionLabel} style={{
            transform: `translateY(${lerp(20, 0, depthP)}px)`,
            opacity: depthP * 2
          }}>01 / Depth</div>
          <h2 className={styles.sectionTitle} style={{
            transform: `translateY(${lerp(30, 0, depthP)}px)`,
            opacity: clamp(depthP * 2.5, 0, 1)
          }}>Layers of Depth</h2>
          <p className={styles.sectionText} style={{
            transform: `translateY(${lerp(20, 0, depthP)}px)`,
            opacity: clamp(depthP * 3, 0, 1)
          }}>
            Every pixel moves at its own pace, creating a sense of depth that draws you deeper into the experience.
          </p>
          <div className={styles.depthDemo}>
            {['Far', 'Mid', 'Near'].map((label, i) => {
              const cardP = progress(scrollY, depthBase + i * 80, depthBase + 400)
              const depth = (0.06 + i * 0.1) * (scrollY - depthBase)
              const rx = lerp(25, 0, cardP)
              const rz = lerp(10 * (i - 1), 0, cardP)
              return (
                <div key={label} className={styles.depthCard} style={{
                  '--depth-index': i,
                  transform: `perspective(600px) rotateX(${rx}deg) rotateZ(${rz}deg) translateY(${depth}px)`,
                  opacity: cardP
                }}>
                  <div className={styles.depthCardInner}>
                    <span className={styles.depthCardLabel}>{label}</span>
                    <div className={styles.depthCardSpeed}>
                      Speed: {(1 + i * 0.8).toFixed(1)}x
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── Section 2: 3D Cards — scroll fan-out ── */}
      <section
        className={`${styles.parallaxSection} ${styles.section3dCards} ${cardsP > 0 ? styles.sectionVisible : ''}`}
        data-section="cards"
        style={{ opacity: cardsP > 0 ? Math.min(cardsP * 3, 1) : 0 }}
      >
        <div className={styles.sectionContent}>
          <div className={styles.sectionLabel} style={{
            transform: `translateY(${lerp(20, 0, cardsP)}px)`,
            opacity: cardsP * 2
          }}>02 / Perspective</div>
          <h2 className={styles.sectionTitle} style={{
            transform: `translateY(${lerp(30, 0, cardsP)}px)`,
            opacity: clamp(cardsP * 2.5, 0, 1)
          }}>Dimensional Cards</h2>
          <p className={styles.sectionText} style={{
            transform: `translateY(${lerp(20, 0, cardsP)}px)`,
            opacity: clamp(cardsP * 3, 0, 1)
          }}>
            Scroll to fan the cards open — each one reacts to both scroll and cursor.
          </p>
          <div className={styles.cards3dGrid}>
            {[
              { title: 'Immersive', icon: '◆', desc: 'Deep engagement through layered visuals', color: 'var(--parallax-coral)' },
              { title: 'Responsive', icon: '◇', desc: 'Every movement creates a reaction', color: 'var(--parallax-amber)' },
              { title: 'Elegant', icon: '○', desc: 'Beauty in every transition and curve', color: 'var(--parallax-rose)' },
              { title: 'Fluid', icon: '△', desc: 'Smooth, natural motion everywhere', color: 'var(--parallax-sage)' },
              { title: 'Alive', icon: '□', desc: 'Interfaces that breathe and respond', color: 'var(--parallax-sand)' },
              { title: 'Harmonious', icon: '☆', desc: 'Every element in perfect balance', color: 'var(--parallax-cream)' }
            ].map((card, i) => {
              const cardP = progress(scrollY, cardsBase + i * 60, cardsBase + 350)
              const fanX = lerp(40 * (i - 2.5), 0, cardP)
              const fanRotY = lerp(15 * (i - 2.5), 0, cardP)
              const fanRotX = lerp(-20, 0, cardP)
              return (
                <div key={card.title} className={styles.card3d} style={{
                  '--card-color': card.color,
                  transform: `perspective(800px) rotateX(${fanRotX + mousePos.y * 4}deg) rotateY(${fanRotY + mousePos.x * 4}deg) translateX(${fanX}px)`,
                  opacity: cardP
                }}>
                  <div className={styles.card3dGlow} />
                  <div className={styles.card3dContent}>
                    <div className={styles.card3dIcon}>{card.icon}</div>
                    <h3 className={styles.card3dTitle}>{card.title}</h3>
                    <p className={styles.card3dDesc}>{card.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── Section 3: Constellation — scroll draws lines ── */}
      <section
        className={`${styles.parallaxSection} ${styles.sectionConstellation} ${constellP > 0 ? styles.sectionVisible : ''}`}
        data-section="constellation"
        style={{ opacity: constellP > 0 ? Math.min(constellP * 3, 1) : 0 }}
      >
        <div className={styles.sectionContent}>
          <div className={styles.sectionLabel} style={{
            transform: `translateY(${lerp(20, 0, constellP)}px)`,
            opacity: constellP * 2
          }}>03 / Connection</div>
          <h2 className={styles.sectionTitle} style={{
            transform: `translateY(${lerp(30, 0, constellP)}px)`,
            opacity: clamp(constellP * 2.5, 0, 1)
          }}>Starlit Connections</h2>
          <p className={styles.sectionText} style={{
            transform: `translateY(${lerp(20, 0, constellP)}px)`,
            opacity: clamp(constellP * 3, 0, 1)
          }}>
            Points of light connect to form constellations — scroll to reveal them.
          </p>
          <div className={styles.constellationScene}>
            <svg className={styles.constellationSvg} viewBox="0 0 800 400" fill="none">
              <defs>
                <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#FF6B6B" stopOpacity="0.6" />
                  <stop offset="50%" stopColor="#FFB347" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#7D9B76" stopOpacity="0.6" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              {[
                { x1:100,y1:200,x2:250,y2:100, t:0.1 },
                { x1:250,y1:100,x2:400,y2:180, t:0.2 },
                { x1:400,y1:180,x2:550,y2:90,  t:0.3 },
                { x1:550,y1:90, x2:700,y2:200, t:0.4 },
                { x1:250,y1:100,x2:350,y2:320, t:0.25 },
                { x1:400,y1:180,x2:500,y2:300, t:0.35 },
                { x1:550,y1:90, x2:650,y2:330, t:0.45 },
                { x1:350,y1:320,x2:500,y2:300, t:0.55 },
                { x1:500,y1:300,x2:650,y2:330, t:0.65 },
              ].map((l, i) => {
                const lineProg = progress(constellP, l.t, l.t + 0.3)
                return <line key={i}
                  x1={l.x1} y1={l.y1}
                  x2={lerp(l.x1, l.x2, lineProg)}
                  y2={lerp(l.y1, l.y2, lineProg)}
                  stroke="url(#lineGrad)" strokeWidth="1.5"
                  opacity={lineProg * 0.7}
                />
              })}
              {[
                [100, 200], [250, 100], [400, 180], [550, 90], [700, 200],
                [350, 320], [500, 300], [650, 330], [180, 280], [470, 50]
              ].map(([cx, cy], i) => {
                const starP = progress(constellP, i * 0.06, i * 0.06 + 0.4)
                return (
                  <g key={i} filter="url(#glow)">
                    <circle cx={cx} cy={cy} r={lerp(0, 4, starP)} fill="#FFB347" opacity={starP * 0.9} />
                    <circle cx={cx} cy={cy} r={lerp(0, 10, starP)} fill="#FFB347" opacity={starP * 0.15} />
                  </g>
                )
              })}
            </svg>
          </div>
        </div>
      </section>

      {/* ── Section 4: Wave ── */}
      <section
        className={`${styles.parallaxSection} ${styles.sectionWave} ${waveP > 0 ? styles.sectionVisible : ''}`}
        data-section="wave"
        style={{ opacity: waveP > 0 ? Math.min(waveP * 3, 1) : 0 }}
      >
        <div className={styles.waveContainer}>
          <svg className={styles.waveSvg} viewBox="0 0 1440 320" preserveAspectRatio="none">
            <defs>
              <linearGradient id="waveGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#FF6B6B" stopOpacity="0.3" />
                <stop offset="50%" stopColor="#FFB347" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#7D9B76" stopOpacity="0.3" />
              </linearGradient>
            </defs>
            <path fill="url(#waveGrad)">
              <animate attributeName="d" dur="8s" repeatCount="indefinite"
                values="
                  M0,160L48,170.7C96,181,192,203,288,197.3C384,192,480,160,576,149.3C672,139,768,149,864,170.7C960,192,1056,224,1152,218.7C1248,213,1344,171,1392,149.3L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z;
                  M0,192L48,186.7C96,181,192,171,288,181.3C384,192,480,224,576,218.7C672,213,768,171,864,154.7C960,139,1056,149,1152,165.3C1248,181,1344,203,1392,213.3L1440,224L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z;
                  M0,160L48,170.7C96,181,192,203,288,197.3C384,192,480,160,576,149.3C672,139,768,149,864,170.7C960,192,1056,224,1152,218.7C1248,213,1344,171,1392,149.3L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"
              />
            </path>
          </svg>
        </div>
        <div className={styles.sectionContent}>
          <div className={styles.sectionLabel} style={{
            transform: `translateY(${lerp(20, 0, waveP)}px)`,
            opacity: waveP * 2
          }}>04 / Flow</div>
          <h2 className={styles.sectionTitle} style={{
            transform: `translateY(${lerp(30, 0, waveP)}px)`,
            opacity: clamp(waveP * 2.5, 0, 1)
          }}>Smooth as Water</h2>
          <p className={styles.sectionText} style={{
            transform: `translateY(${lerp(20, 0, waveP)}px)`,
            opacity: clamp(waveP * 3, 0, 1)
          }}>
            Transitions flow naturally, like water finding its path.
            Every animation is carefully crafted to feel organic and alive.
          </p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        <div className={styles.footerContent}>
          <p className={styles.footerText}>
            Crafted with passion for beautiful experiences
          </p>
          <div className={styles.footerShapes}>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className={styles.footerShape} style={{
                '--shape-delay': `${i * 0.2}s`,
                '--shape-color': [
                  'var(--parallax-coral)', 'var(--parallax-amber)',
                  'var(--parallax-rose)', 'var(--parallax-sage)', 'var(--parallax-sand)'
                ][i]
              }} />
            ))}
          </div>
        </div>
      </footer>
    </div>
  )
}
