/* =========================================================
   CANAL 93 — APP.JS
   Animations, micro-interactions, countdown, mobile nav
   ========================================================= */

(() => {
  'use strict';

  // ============ PAGE LOAD ============
  window.addEventListener('load', () => {
    const loader = document.getElementById('pageLoad');
    setTimeout(() => {
      loader?.classList.add('done');
      document.getElementById('hero')?.classList.add('loaded');
    }, 1100);
  });

  // ============ HEADER SCROLL ============
  const header = document.getElementById('siteHeader');
  let lastScroll = 0;
  const onScroll = () => {
    const y = window.scrollY;
    if (y > 40) header?.classList.add('scrolled');
    else header?.classList.remove('scrolled');
    lastScroll = y;
  };
  window.addEventListener('scroll', onScroll, { passive: true });

  // ============ OVERLAY NAV (side panel) ============
  const burger = document.getElementById('burgerBtn');
  const closeBtn = document.getElementById('overlayClose');
  const overlay = document.getElementById('overlayNav');
  // Ensure backdrop element exists
  let backdrop = document.getElementById('overlayNavBackdrop');
  if (!backdrop && overlay) {
    backdrop = document.createElement('div');
    backdrop.id = 'overlayNavBackdrop';
    backdrop.className = 'overlay-nav-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    overlay.parentNode.insertBefore(backdrop, overlay);
  }

  let savedScrollY = 0;
  const openNav = () => {
    savedScrollY = window.scrollY;
    overlay?.classList.add('open');
    backdrop?.classList.add('open');
    overlay?.setAttribute('aria-hidden', 'false');
    burger?.setAttribute('aria-expanded', 'true');
    document.body.style.position = 'fixed';
    document.body.style.top = `-${savedScrollY}px`;
    document.body.style.left = '0';
    document.body.style.right = '0';
    document.body.style.width = '100%';
  };
  const closeNav = () => {
    overlay?.classList.remove('open');
    backdrop?.classList.remove('open');
    overlay?.setAttribute('aria-hidden', 'true');
    burger?.setAttribute('aria-expanded', 'false');
    const prevBehavior = document.documentElement.style.scrollBehavior;
    document.documentElement.style.scrollBehavior = 'auto';
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.left = '';
    document.body.style.right = '';
    document.body.style.width = '';
    window.scrollTo(0, savedScrollY);
    requestAnimationFrame(() => {
      document.documentElement.style.scrollBehavior = prevBehavior;
    });
  };
  // Block touchmove on backdrop so the page below doesn't scroll
  backdrop?.addEventListener('touchmove', (e) => e.preventDefault(), { passive: false });

  burger?.addEventListener('click', openNav);
  backdrop?.addEventListener('click', closeNav);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay?.classList.contains('open')) closeNav();
  });

  // Search button — slide-down inline search bar
  const searchBtn = document.getElementById('searchBtn');
  const searchBar = document.getElementById('searchBar');
  const searchInput = document.getElementById('searchInput');
  const searchClose = document.getElementById('searchClose');
  const searchForm = document.getElementById('searchForm');

  const openSearch = () => {
    searchBar?.classList.add('open');
    searchBar?.setAttribute('aria-hidden', 'false');
    setTimeout(() => searchInput?.focus(), 50);
  };
  const closeSearch = () => {
    searchBar?.classList.remove('open');
    searchBar?.setAttribute('aria-hidden', 'true');
    if (searchInput) searchInput.value = '';
  };

  searchBtn?.addEventListener('click', () => {
    if (searchBar?.classList.contains('open')) closeSearch();
    else openSearch();
  });
  searchClose?.addEventListener('click', closeSearch);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && searchBar?.classList.contains('open')) closeSearch();
    if ((e.key === '/' || (e.metaKey && e.key === 'k')) && !searchBar?.classList.contains('open')) {
      const tag = document.activeElement?.tagName;
      if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
        e.preventDefault();
        openSearch();
      }
    }
  });
  // Search index — maps keywords to destination pages
  const searchIndex = [
    { url: 'studios-repetition.html', kw: ['studio répétition', 'studios répétition', 'répétition', 'repetition', 'répéter', 'repeter', 'tarif studio', 'forfait', 'groupe', 'solo studio', 'duo studio', 'adhésion studio'] },
    { url: 'studio-enregistrement.html', kw: ['studio enregistrement', 'enregistrement', 'enregistrer', 'enreg', 'recording', 'studio audio', 'neumann', 'mixage', 'master', 'pro tools', 'ableton', 'ingé son', 'ingenieur son'] },
    { url: 'studio-danse.html', kw: ['studio danse', 'studios danse', 'danse', 'danser', 'choré', 'chorégraphie', 'mouvement', 'parquet', 'miroir'] },
    { url: 'grande-salle.html', kw: ['grande salle', 'salle de concert', 'salle 363', '363 places', 'capacité', 'live', 'privatisation salle', 'régie son lumière'] },
    { url: 'agenda.html', kw: ['agenda', 'billetterie', 'billet', 'place', 'tickets', 'concert', 'programmation', 'dates', 'à venir', 'a venir', 'weezevent', 'yaniss', 'odua', 'nayra', 'samira', 'brahmia', 'chazil', 'blvr', 'haze', 'musazi', 'trinity rebel', 'pink casbah'] },
    { url: 'terre-hip-hop.html', kw: ['terre hip hop', 'terre hip-hop', 'hip hop', 'hip-hop', 'rap contest', 'open mic', 'freestyle', 'trap', 'drill', 'boom bap', 'contest', 'open-mic'] },
    { url: 'ateliers.html', kw: ['atelier', 'ateliers', 'atelier musique', 'cours', 'cours de musique', 'piano', 'guitare', 'chant', 'batterie', 'basse', 'apprendre', 'instrument', 'britto', 'hermine', 'baptiste', 'greg', 'tom'] },
    { url: 'masterclass.html', kw: ['masterclass', 'master class', "maad'sterclass", 'maadsterclass', 'raï', 'rai', 'fanfare', 'super raï band', '93 super raï band', 'touvet', 'samir inal', 'chaabi'] },
    { url: 'residences.html', kw: ['résidence', 'résidences', 'residence', 'residences', 'artiste associé', 'artiste-associée', 'prichia', 'treizes', 'nakk mendosa', 'nakk', 'ryaam', 'thielo', 'résidence création'] },
    { url: 'actions-culturelles.html', kw: ['action culturelle', 'actions culturelles', 'scolaire', 'école', 'ecole', 'collège', 'college', 'lycée', 'lycee', 'université', 'universite', 'sorbonne', 'pédagogie', 'pedagogie', 'transmission', 'campus dance floor', 'marie curie', 'sharouh'] },
    { url: 'le-projet.html', kw: ['projet', 'mission', 'identité', 'identite', 'valeurs', '2002', 'historique', 'diffusion', 'accompagnement', 'transmission projet'] },
    { url: 'le-lieu.html', kw: ['le lieu', 'lieu', 'espace', 'espaces', 'bâtiment', 'batiment', 'architecture', 'plan'] },
    { url: 'infos-pratiques.html', kw: ['infos pratiques', 'infos', 'pratique', 'accès', 'acces', 'métro', 'metro', 'transport', 'transports', 'bus', 'tram', 'tramway', 'adresse', 'horaires', 'horaire', 'adhésion', 'adhesion'] },
    { url: 'contact.html', kw: ['contact', 'contacter', 'email', 'téléphone', 'telephone', 'message', 'communication', 'formulaire'] },
    { url: 'photos.html', kw: ['photo', 'photos', 'galerie', 'images', 'vidéo', 'video', 'medias'] },
    { url: 'fiches-techniques.html', kw: ['fiche technique', 'fiches techniques', 'régie', 'regie', 'production', 'son lumière', 'son lumiere', 'tech', 'patch', 'backline', 'loges', 'plan scène', 'plan scene', 'espace pro'] },
    { url: 'privatisation.html', kw: ['privatisation', 'privatiser', 'louer', 'location', 'événement entreprise', 'evenement entreprise', 'séminaire', 'seminaire', 'devis', 'showcase'] },
    { url: 'espace-membre.html', kw: ['membre', 'adhérer', 'adherer', 'login', 'connexion', 'compte', 'inscription', 'espace membre'] },
  ];

  const norm = s => s.toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ').trim();

  const searchSite = (query) => {
    const q = norm(query);
    if (!q) return null;
    let best = null;
    let bestScore = 0;
    searchIndex.forEach(entry => {
      let score = 0;
      entry.kw.forEach(kw => {
        const nkw = norm(kw);
        if (q === nkw) score += 200;            // exact match
        else if (q.startsWith(nkw + ' ') || q.endsWith(' ' + nkw) || q === nkw) score += 120;
        else if ((' ' + q + ' ').includes(' ' + nkw + ' ')) score += 100;  // word boundary
        else if (q.includes(nkw)) score += 60;  // contains keyword
        else if (nkw.includes(q) && q.length >= 3) score += 40;  // keyword contains query
      });
      if (score > bestScore) { bestScore = score; best = entry; }
    });
    return best ? best.url : null;
  };

  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = searchInput?.value.trim();
    if (!q) return;
    const target = searchSite(q);
    if (target) {
      window.location.href = target;
    } else {
      // Fallback: show a hint and don't navigate
      if (searchInput) {
        searchInput.value = '';
        searchInput.placeholder = `Aucun résultat pour « ${q} » — essaie : studios, ateliers, concerts…`;
        setTimeout(() => {
          searchInput.placeholder = 'Rechercher un concert, un studio, un artiste…';
        }, 4000);
      }
    }
  });

  // ============ THEME TOGGLE ============
  const applyTheme = (theme) => {
    if (theme === 'light') document.body.classList.add('light-theme');
    else document.body.classList.remove('light-theme');
    document.querySelectorAll('.theme-toggle button').forEach(btn => {
      const isActive = btn.dataset.theme === theme;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
    try { localStorage.setItem('c93-theme', theme); } catch (e) {}
  };
  const savedTheme = (() => { try { return localStorage.getItem('c93-theme'); } catch (e) { return null; } })();
  if (savedTheme === 'light') applyTheme('light');
  document.querySelectorAll('.theme-toggle button').forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });
  closeBtn?.addEventListener('click', closeNav);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeNav(); });
  overlay?.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', (e) => {
      const href = a.getAttribute('href');
      if (!href || href.startsWith('http')) return closeNav();
      if (href.startsWith('#')) closeNav();
      // For internal links to other pages, let browser navigate naturally (closeNav not needed)
    });
  });

  // ============ REVEAL ON SCROLL ============
  const revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -60px 0px' });
    revealEls.forEach(el => io.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('in'));
  }

  // ============ AUTO MICRO-ANIMATIONS (titles, cards, descriptions) ============
  const autoSelector = 'h1, h2, h3, .page-hero p.lede, .section-head .lede, .page-prose > p, .info-card, .event-card, .studio-card, .thh-prize, .timeline-item, .quote, .photo-slide, .date-item, .price-row, .stat';
  const autoEls = document.querySelectorAll(autoSelector);

  if ('IntersectionObserver' in window && window.matchMedia('(prefers-reduced-motion: no-preference)').matches) {
    // Activate the body class so CSS pre-hides elements BEFORE we observe them
    document.body.classList.add('js-anim');

    // Then wait two frames (one for CSS apply, one to settle) before triggering
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const ioAuto = new IntersectionObserver((entries) => {
          entries.forEach(e => {
            if (e.isIntersecting) {
              // Stagger slightly by index in case multiple elements are visible
              const delay = Math.min(e.target.dataset.animIdx ? +e.target.dataset.animIdx * 100 : 0, 500);
              setTimeout(() => e.target.classList.add('anim-in'), delay);
              ioAuto.unobserve(e.target);
            }
          });
        }, { threshold: 0, rootMargin: '0px 0px -20% 0px' });

        // Tag stagger index inside grids before observing
        document.querySelectorAll('.info-grid, .prog-grid, .studios-grid, .stats-grid, .thh-prizes, .date-list, .timeline').forEach(grid => {
          [...grid.children].forEach((child, idx) => {
            child.dataset.animIdx = idx;
          });
        });

        autoEls.forEach(el => {
          if (el.closest('.site-header, .overlay-nav-head, .footer-bottom')) return;
          ioAuto.observe(el);
        });
      });
    });
  } else {
    autoEls.forEach(el => el.classList.add('anim-in'));
  }

  // ============ COUNTDOWN ============
  const cdEls = document.querySelectorAll('[data-cd]');
  const updateCd = () => {
    const now = Date.now();
    cdEls.forEach(el => {
      const target = new Date(el.dataset.cd).getTime();
      const diff = target - now;
      if (diff <= 0) { el.textContent = 'LIVE'; return; }
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      el.textContent = `${d}j · ${String(h).padStart(2,'0')}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`;
    });
  };
  if (cdEls.length) {
    updateCd();
    setInterval(updateCd, 1000);
  }

  // ============ PHOTO SLIDER (continuous smooth flow) ============
  const track = document.getElementById('photoTrack');
  if (track) {
    const originalSlides = [...track.querySelectorAll('.photo-slide')];
    const total = originalSlides.length;
    const currentEl = document.getElementById('photoCurrent');
    const progressEl = document.getElementById('photoProgress');
    const prevBtn = document.getElementById('photoPrev');
    const nextBtn = document.getElementById('photoNext');

    // Duplicate slides for seamless loop
    originalSlides.forEach(s => {
      const clone = s.cloneNode(true);
      clone.setAttribute('aria-hidden', 'true');
      track.appendChild(clone);
    });
    // Force CSS scroll-snap off so it doesn't fight the continuous animation
    track.style.scrollSnapType = 'none';

    const slides = [...track.querySelectorAll('.photo-slide')];

    let halfWidth = 0;
    const recalc = () => {
      let w = 0;
      for (let i = 0; i < total; i++) {
        const s = slides[i];
        const style = getComputedStyle(s);
        w += s.offsetWidth + parseFloat(style.marginRight || 0);
      }
      // Add the gap between slides (column-gap on flex)
      const gap = parseFloat(getComputedStyle(track).columnGap || getComputedStyle(track).gap || 0);
      halfWidth = w + gap * total;
    };
    recalc();
    window.addEventListener('resize', recalc);

    const speed = 1.1; // px per frame ~ 66px/sec — défilement fluide bien visible
    let rafId = null;
    let paused = false;
    let userInteracting = false;

    const updateUI = () => {
      const left = track.scrollLeft % (halfWidth || 1);
      // approximate current slide
      let cum = 0;
      let idx = 0;
      for (let i = 0; i < total; i++) {
        const s = slides[i];
        const w = s.offsetWidth + parseFloat(getComputedStyle(track).columnGap || 0);
        if (left < cum + w / 2) { idx = i; break; }
        cum += w;
        idx = i;
      }
      const num = idx + 1;
      if (currentEl) currentEl.textContent = String(num).padStart(2, '0');
      if (progressEl) progressEl.style.width = ((num / total) * 100) + '%';
    };

    const tick = () => {
      if (!paused && !userInteracting) {
        track.scrollLeft += speed;
        if (track.scrollLeft >= halfWidth) {
          track.scrollLeft -= halfWidth;
        }
        updateUI();
      }
      rafId = requestAnimationFrame(tick);
    };

    // Manual buttons jump by one slide width
    const slideStep = () => slides[0]?.offsetWidth + parseFloat(getComputedStyle(track).columnGap || 0);
    prevBtn?.addEventListener('click', () => {
      paused = true;
      track.scrollBy({ left: -slideStep(), behavior: 'smooth' });
      setTimeout(() => { paused = false; }, 700);
    });
    nextBtn?.addEventListener('click', () => {
      paused = true;
      track.scrollBy({ left: slideStep(), behavior: 'smooth' });
      setTimeout(() => { paused = false; }, 700);
    });

    // Pause on user interaction — uniquement vrai swipe horizontal / wheel,
    // pour ne pas freezer le défilement quand l'utilisateur scrolle la page verticalement
    let interactionTimeout = null;
    let tStartX = 0, tStartY = 0;
    const pauseFor = (ms = 1500) => {
      userInteracting = true;
      clearTimeout(interactionTimeout);
      interactionTimeout = setTimeout(() => { userInteracting = false; }, ms);
    };
    track.addEventListener('wheel', () => pauseFor(1500), { passive: true });
    track.addEventListener('touchstart', (e) => {
      tStartX = e.touches[0].clientX;
      tStartY = e.touches[0].clientY;
    }, { passive: true });
    track.addEventListener('touchmove', (e) => {
      const dx = Math.abs(e.touches[0].clientX - tStartX);
      const dy = Math.abs(e.touches[0].clientY - tStartY);
      // Vrai swipe horizontal : dx dominant et significatif
      if (dx > 14 && dx > dy * 1.4) pauseFor(1500);
    }, { passive: true });

    // Pause on hover (desktop)
    track.addEventListener('mouseenter', () => { paused = true; });
    track.addEventListener('mouseleave', () => { paused = false; });

    // Pause when slider out of viewport
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach(e => { paused = !e.isIntersecting; });
      }, { threshold: 0.15 });
      io.observe(track);
    }

    updateUI();
    rafId = requestAnimationFrame(tick);
  }

  // ============ CHIPS FILTER (visual) ============
  document.querySelectorAll('.prog-controls .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chip.parentElement.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
    });
  });

  // ============ SMOOTH ANCHOR SCROLL OFFSET ============
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', (e) => {
      const href = a.getAttribute('href');
      if (!href || href === '#') return;
      const t = document.querySelector(href);
      if (!t) return;
      e.preventDefault();
      const offset = 60;
      const y = t.getBoundingClientRect().top + window.pageYOffset - offset;
      window.scrollTo({ top: y, behavior: 'smooth' });
    });
  });

  // ============ GSAP ANIMATIONS ============
  if (window.gsap) {
    gsap.registerPlugin(ScrollTrigger);

    // Hero title staggered reveal (safe: animates current → current, not from 0)
    gsap.fromTo('.hero-title',
      { y: 80, opacity: 0 },
      { y: 0, opacity: 1, duration: 1.2, delay: 0.5, ease: 'power3.out' }
    );

    // Parallax hero media
    gsap.to('.hero-media img', {
      yPercent: 18,
      ease: 'none',
      scrollTrigger: {
        trigger: '.hero',
        start: 'top top',
        end: 'bottom top',
        scrub: true
      }
    });

    // Section heads counter-rise
    gsap.utils.toArray('.section-head h2').forEach(h => {
      gsap.from(h, {
        y: 60,
        opacity: 0,
        duration: 0.9,
        ease: 'power3.out',
        scrollTrigger: { trigger: h, start: 'top 85%' }
      });
    });

    // Marquee speed up on hover
    const marqueeTrack = document.querySelector('.marquee-track');
    if (marqueeTrack) {
      const marquee = marqueeTrack.parentElement;
      marquee.addEventListener('mouseenter', () => marqueeTrack.style.animationDuration = '14s');
      marquee.addEventListener('mouseleave', () => marqueeTrack.style.animationDuration = '32s');
    }

    // Stat counter
    gsap.utils.toArray('.stat .num').forEach(numEl => {
      const raw = numEl.textContent.trim();
      const numMatch = raw.match(/(\d+)/);
      if (!numMatch) return;
      const finalVal = parseInt(numMatch[1], 10);
      const suffix = raw.replace(numMatch[1], '');
      const obj = { v: 0 };
      gsap.to(obj, {
        v: finalVal,
        duration: 1.6,
        ease: 'power2.out',
        scrollTrigger: { trigger: numEl, start: 'top 88%' },
        onUpdate: () => { numEl.textContent = Math.round(obj.v) + suffix; }
      });
    });

    // ============ PHASE 2 MOTION ============
    // Hero-next concerts strip: stagger reveal from bottom
    gsap.from('.hero-next-card', {
      y: 28,
      opacity: 0,
      duration: 0.7,
      stagger: 0.09,
      ease: 'power3.out',
      delay: 1.1
    });

    // Grid items stagger reveal (event cards, studio cards, info cards) — cinematic
    ['.prog-grid', '.studios-grid', '.info-grid'].forEach(sel => {
      const grid = document.querySelector(sel);
      if (!grid) return;
      const children = [...grid.children].filter(c => !c.classList.contains('featured-slider'));
      if (!children.length) return;
      gsap.fromTo(children,
        { y: 70, opacity: 0, scale: 0.97, filter: 'blur(6px)' },
        { y: 0, opacity: 1, scale: 1, filter: 'blur(0px)',
          duration: 1.2, stagger: 0.12,
          ease: 'expo.out',
          scrollTrigger: { trigger: grid, start: 'top 85%' }
        }
      );
    });

    // Featured slider reveal — rapide (la 1ère card doit apparaître vite, surtout mobile)
    const fSliderEl = document.getElementById('featuredSlider');
    if (fSliderEl) {
      gsap.fromTo(fSliderEl,
        { y: 28, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.55, ease: 'power2.out',
          scrollTrigger: { trigger: fSliderEl, start: 'top 100%' }
        }
      );
    }

    // Subtle parallax on event-card images on scroll (mild)
    gsap.utils.toArray('.prog-grid .event-card:not(.event-featured) .card-media img').forEach(img => {
      gsap.to(img, {
        yPercent: -5,
        ease: 'none',
        scrollTrigger: {
          trigger: img,
          start: 'top bottom',
          end: 'bottom top',
          scrub: 1.2
        }
      });
    });

    // Eyebrow numbers reveal (01 — Programmation etc)
    gsap.utils.toArray('.section-head .eyebrow').forEach(eb => {
      gsap.from(eb, {
        x: -20,
        opacity: 0,
        duration: 0.6,
        ease: 'power2.out',
        scrollTrigger: { trigger: eb, start: 'top 88%' }
      });
    });

    // Studio card subtle parallax on image
    gsap.utils.toArray('.studio-card img').forEach(img => {
      gsap.to(img, {
        yPercent: -6,
        ease: 'none',
        scrollTrigger: {
          trigger: img,
          start: 'top bottom',
          end: 'bottom top',
          scrub: true
        }
      });
    });

    // Marquee scrolltrigger: speed up on scroll velocity
    const marqueeEl = document.querySelector('.marquee-track');
    if (marqueeEl) {
      let scrollVel = 0;
      ScrollTrigger.create({
        onUpdate: (self) => {
          scrollVel = Math.min(Math.abs(self.getVelocity() / 600), 4);
          gsap.to(marqueeEl, { timeScale: 1 + scrollVel, overwrite: 'auto', duration: 0.4 });
        }
      });
    }

    // Timeline items: slide-in from left in sequence
    gsap.utils.toArray('.timeline-item').forEach((item, i) => {
      gsap.from(item, {
        x: -30,
        opacity: 0,
        duration: 0.7,
        ease: 'power3.out',
        scrollTrigger: { trigger: item, start: 'top 85%' }
      });
    });
  }

  // ============ IMMERSIVE CONCERTS SHOWCASE ============
  const showcase = document.getElementById('concertsShowcase');
  const posterRail = document.getElementById('posterRail');
  if (showcase && posterRail) {
    const posters = [...posterRail.querySelectorAll('.poster')];
    const total = posters.length;
    const showcaseBg = document.getElementById('showcaseBg');
    const counterCur = document.getElementById('showcaseCurrent');
    const counterTot = document.getElementById('showcaseTotal');
    const navPrev = document.getElementById('showcasePrev');
    const navNext = document.getElementById('showcaseNext');

    if (counterTot) counterTot.textContent = String(total).padStart(2, '0');

    // Set initial per-poster --poster-color for ticket button + glow
    posters.forEach(p => {
      const c = p.dataset.color || 'var(--accent)';
      p.style.setProperty('--poster-color', c);
    });

    let activeIdx = 0;
    const setActive = (i) => {
      activeIdx = Math.max(0, Math.min(total - 1, i));
      posters.forEach((p, idx) => p.classList.toggle('is-active', idx === activeIdx));
      if (counterCur) counterCur.textContent = String(activeIdx + 1).padStart(2, '0');
      const color = posters[activeIdx]?.dataset.color || '#c6f432';
      showcase.style.setProperty('--showcase-color', color);
    };

    // Detect active poster as the one closest to viewport center of rail
    let raf = null;
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = null;
        const railRect = posterRail.getBoundingClientRect();
        const railCenterX = railRect.left + railRect.width / 2;
        let best = 0;
        let bestDist = Infinity;
        posters.forEach((p, idx) => {
          const r = p.getBoundingClientRect();
          const cx = r.left + r.width / 2;
          const d = Math.abs(cx - railCenterX);
          if (d < bestDist) { bestDist = d; best = idx; }
        });
        if (best !== activeIdx) setActive(best);
      });
    };
    posterRail.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);

    const scrollToIndex = (i) => {
      const target = posters[Math.max(0, Math.min(total - 1, i))];
      if (!target) return;
      const railRect = posterRail.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const delta = (targetRect.left - railRect.left) - (railRect.width - targetRect.width) / 2;
      posterRail.scrollBy({ left: delta, behavior: 'smooth' });
    };

    navPrev?.addEventListener('click', () => scrollToIndex(activeIdx - 1));
    navNext?.addEventListener('click', () => scrollToIndex(activeIdx + 1));

    // Click poster → scroll-center it
    posters.forEach((p, idx) => {
      p.addEventListener('click', (e) => {
        if (e.target.closest('.p-ticket')) return; // don't intercept button
        if (idx !== activeIdx) {
          e.preventDefault();
          scrollToIndex(idx);
        }
      });
    });

    // Keyboard arrows
    showcase.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') { e.preventDefault(); scrollToIndex(activeIdx - 1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); scrollToIndex(activeIdx + 1); }
    });

    // Mouse parallax tilt on poster frames (desktop only)
    if (window.matchMedia('(hover:hover)').matches) {
      posters.forEach(p => {
        const frame = p.querySelector('.poster-frame');
        const img = p.querySelector('.poster-frame img');
        p.addEventListener('mousemove', (e) => {
          const r = p.getBoundingClientRect();
          const x = (e.clientX - r.left) / r.width - 0.5;  // -0.5 .. 0.5
          const y = (e.clientY - r.top) / r.height - 0.5;
          if (frame) frame.style.transform = `perspective(900px) rotateY(${x * 6}deg) rotateX(${-y * 5}deg) translateY(-6px)`;
          if (img) img.style.transformOrigin = `${50 + x * 10}% ${50 + y * 10}%`;
        });
        p.addEventListener('mouseleave', () => {
          if (frame) frame.style.transform = '';
          if (img) img.style.transformOrigin = '';
        });
      });
    }

    // Initial active = first poster, then center it via scroll
    requestAnimationFrame(() => {
      setActive(0);
      onScroll();
    });
  }

  // ============ CURSOR SPOTLIGHT — featured slider ============
  if (window.matchMedia('(hover:hover)').matches) {
    document.querySelectorAll('.featured-slide .card-media').forEach(media => {
      // Inject spotlight overlay
      if (!media.querySelector('.spotlight')) {
        const sp = document.createElement('div');
        sp.className = 'spotlight';
        media.appendChild(sp);
      }
      media.addEventListener('mousemove', (e) => {
        const rect = media.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        media.style.setProperty('--mx', x + '%');
        media.style.setProperty('--my', y + '%');
      });
    });
  }

  // ============ FEATURED SLIDER (À l'affiche cycling) ============
  const fSlider = document.getElementById('featuredSlider');
  if (fSlider) {
    const slides = [...fSlider.querySelectorAll('.featured-slide')];
    const dots = [...fSlider.querySelectorAll('.fd-dot')];
    const bar = document.getElementById('featuredProgressBar');
    const interval = parseInt(fSlider.dataset.autoplay || '5200', 10);
    let current = 0;
    let timer = null;
    let progressStart = 0;
    let rafId = null;
    let paused = false;

    const showAt = (i) => {
      const next = (i + slides.length) % slides.length;
      if (next === current) return;
      // Mark current as "was-active" so it slides down out of frame
      slides.forEach((s, idx) => {
        s.classList.remove('was-active');
        if (idx === current) s.classList.add('was-active');
      });
      // Mark the new active
      slides.forEach((s, idx) => s.classList.toggle('active', idx === next));
      dots.forEach((d, idx) => d.classList.toggle('active', idx === next));
      current = next;
      progressStart = performance.now();
      if (bar) bar.style.width = '0%';
      // Clean was-active after transition so it's ready to come from top again
      setTimeout(() => {
        slides.forEach((s, idx) => { if (idx !== current) s.classList.remove('was-active'); });
      }, 950);
    };

    const tickProgress = () => {
      if (paused || !bar) { rafId = requestAnimationFrame(tickProgress); return; }
      const elapsed = performance.now() - progressStart;
      const pct = Math.min((elapsed / interval) * 100, 100);
      bar.style.width = pct + '%';
      rafId = requestAnimationFrame(tickProgress);
    };

    const start = () => {
      stop();
      timer = setInterval(() => { if (!paused) showAt(current + 1); }, interval);
    };
    const stop = () => { if (timer) { clearInterval(timer); timer = null; } };

    dots.forEach(d => {
      d.addEventListener('click', () => {
        const i = parseInt(d.dataset.i, 10);
        showAt(i);
        start(); // restart timer
      });
    });

    const setPaused = (p) => {
      if (paused === p) return;
      paused = p;
      if (!paused) {
        // Restart progress + timer cleanly when resuming
        progressStart = performance.now();
        if (bar) bar.style.width = '0%';
        start();
      }
    };
    // Pause on hover — UNIQUEMENT sur devices avec hover réel (souris).
    // Sur iPhone/Android, mouseenter se déclenche au tap mais mouseleave ne fire jamais
    // → slider en pause permanente. Le check (hover: hover) empêche ce bug mobile.
    if (window.matchMedia && window.matchMedia('(hover: hover)').matches) {
      fSlider.addEventListener('mouseenter', () => setPaused(true));
      fSlider.addEventListener('mouseleave', () => setPaused(false));
    }
    document.addEventListener('visibilitychange', () => setPaused(document.hidden));

    // Pause when out of viewport
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach(e => setPaused(!e.isIntersecting));
      }, { threshold: 0.25 });
      io.observe(fSlider);
    }

    // Touch swipe support
    let touchX = 0;
    fSlider.addEventListener('touchstart', (e) => { touchX = e.touches[0].clientX; }, { passive: true });
    fSlider.addEventListener('touchend', (e) => {
      const dx = e.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 40) {
        showAt(current + (dx < 0 ? 1 : -1));
        start();
      }
    });

    showAt(0);
    start();
    rafId = requestAnimationFrame(tickProgress);
  }

  // ============ VIDEO MODAL ============
  const videoModal = document.getElementById('videoModal');
  const videoIframe = document.getElementById('videoModalIframe');
  const videoClose = document.getElementById('videoModalClose');
  if (videoModal && videoIframe) {
    const openVideo = (url) => {
      videoIframe.src = url;
      videoModal.classList.add('open');
      videoModal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    };
    const closeVideo = () => {
      videoModal.classList.remove('open');
      videoModal.setAttribute('aria-hidden', 'true');
      videoIframe.src = '';
      document.body.style.overflow = '';
    };
    document.querySelectorAll('.btn-play[data-video]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        openVideo(btn.dataset.video);
      });
    });
    videoClose?.addEventListener('click', closeVideo);
    videoModal.addEventListener('click', (e) => {
      if (e.target === videoModal) closeVideo();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && videoModal.classList.contains('open')) closeVideo();
    });
  }

  // ============ LIGHTBOX (photo gallery) ============
  const lightbox = document.getElementById('lightbox');
  const lbImg = document.getElementById('lightboxImg');
  const lbNum = document.getElementById('lightboxNum');
  const lbLabel = document.getElementById('lightboxLabel');
  const lbClose = document.getElementById('lightboxClose');
  const lbPrev = document.getElementById('lightboxPrev');
  const lbNext = document.getElementById('lightboxNext');
  if (lightbox && lbImg) {
    // Collect ORIGINAL photo slides only (skip the cloned duplicates from photo slider)
    const slidesRoot = document.getElementById('photoTrack');
    const allSlides = slidesRoot ? [...slidesRoot.querySelectorAll('.photo-slide')] : [];
    // Filter to slides that are NOT aria-hidden (clones have aria-hidden=true)
    const origSlides = allSlides.filter(s => s.getAttribute('aria-hidden') !== 'true');
    let lbIndex = 0;

    const showAt = (i) => {
      if (!origSlides.length) return;
      lbIndex = (i + origSlides.length) % origSlides.length;
      const slide = origSlides[lbIndex];
      const img = slide.querySelector('img');
      const num = slide.querySelector('.photo-slide-caption .num');
      const label = slide.querySelector('.photo-slide-caption .label');
      if (img) {
        lbImg.src = img.src;
        lbImg.alt = img.alt || '';
      }
      if (num) lbNum.textContent = num.textContent;
      if (label) lbLabel.textContent = label.textContent;
    };
    const openLb = (i) => {
      showAt(i);
      lightbox.classList.add('open');
      lightbox.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    };
    const closeLb = () => {
      lightbox.classList.remove('open');
      lightbox.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    };
    allSlides.forEach((slide) => {
      slide.addEventListener('click', (e) => {
        // Avoid triggering on drag (when user swipes the slider)
        if (slide.dataset.dragging === 'true') return;
        const origIndex = origSlides.indexOf(slide);
        const idx = origIndex >= 0 ? origIndex : (allSlides.indexOf(slide) % origSlides.length);
        openLb(idx);
      });
    });
    lbClose?.addEventListener('click', closeLb);
    lbPrev?.addEventListener('click', () => showAt(lbIndex - 1));
    lbNext?.addEventListener('click', () => showAt(lbIndex + 1));
    lightbox.addEventListener('click', (e) => {
      if (e.target === lightbox) closeLb();
    });
    document.addEventListener('keydown', (e) => {
      if (!lightbox.classList.contains('open')) return;
      if (e.key === 'Escape') closeLb();
      else if (e.key === 'ArrowLeft') showAt(lbIndex - 1);
      else if (e.key === 'ArrowRight') showAt(lbIndex + 1);
    });
  }

  // ============ MAGNETIC BUTTONS (desktop only) ============
  if (window.matchMedia('(hover:hover)').matches) {
    document.querySelectorAll('.btn-primary, .hero-actions .btn, .header-cta .icon-btn, .burger').forEach(btn => {
      const strength = btn.classList.contains('icon-btn') || btn.classList.contains('burger') ? 0.25 : 0.18;
      // Combine magnetic offset with the hover lift (-2px y)
      btn.addEventListener('mousemove', (e) => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        btn.style.transform = `translate(${x * strength}px, ${(y * strength) - 2}px)`;
      });
      btn.addEventListener('mouseleave', () => {
        btn.style.transform = '';
      });
    });
  }

  // ============ STICKY MOBILE CTA ============
  const stickyCta = document.getElementById('stickyCta');
  if (stickyCta) {
    let lastY = 0;
    const toggleSticky = () => {
      const y = window.scrollY;
      // Show after passing hero (~600px) AND when scrolling
      if (y > 700) {
        stickyCta.classList.add('show');
        stickyCta.setAttribute('aria-hidden', 'false');
      } else {
        stickyCta.classList.remove('show');
        stickyCta.setAttribute('aria-hidden', 'true');
      }
      lastY = y;
    };
    window.addEventListener('scroll', toggleSticky, { passive: true });
    toggleSticky();
  }

  // ============ BACK TO TOP ============
  const backTop = document.getElementById('backToTop');
  if (backTop) {
    const toggleBackTop = () => {
      if (window.scrollY > 600) backTop.classList.add('show');
      else backTop.classList.remove('show');
    };
    window.addEventListener('scroll', toggleBackTop, { passive: true });
    backTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    toggleBackTop();
  }

  // ============ CURSOR FOLLOWER (subtle, desktop only) ============
  if (window.matchMedia('(hover:hover)').matches) {
    const cursor = document.createElement('div');
    cursor.style.cssText = `
      position:fixed;width:24px;height:24px;border:1px solid rgba(198,244,50,0.6);
      border-radius:50%;pointer-events:none;z-index:9999;
      transform:translate(-50%,-50%) scale(1);
      transition:transform 220ms cubic-bezier(.22,1,.36,1),background 180ms,border-color 180ms;
      mix-blend-mode:difference;
    `;
    document.body.appendChild(cursor);
    let mx = 0, my = 0, cx = 0, cy = 0;
    document.addEventListener('mousemove', (e) => { mx = e.clientX; my = e.clientY; });
    const tick = () => {
      cx += (mx - cx) * 0.18;
      cy += (my - cy) * 0.18;
      cursor.style.left = cx + 'px';
      cursor.style.top = cy + 'px';
      requestAnimationFrame(tick);
    };
    tick();
    document.querySelectorAll('a, button, .card, .studio-card, .chip').forEach(el => {
      el.addEventListener('mouseenter', () => cursor.style.transform = 'translate(-50%,-50%) scale(2.2)');
      el.addEventListener('mouseleave', () => cursor.style.transform = 'translate(-50%,-50%) scale(1)');
    });
  }

})();
