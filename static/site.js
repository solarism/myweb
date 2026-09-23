'use strict';
const menuButton = document.querySelector('.menu-toggle');
const nav = document.querySelector('.nav-links');
menuButton.addEventListener('click', () => {
  const expanded = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(expanded));
  nav.classList.toggle('is-open', expanded);
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('is-open');
  menuButton.setAttribute('aria-expanded', 'false');
}));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && nav.classList.contains('is-open')) {
    nav.classList.remove('is-open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.focus();
  }
});
const languageLink = document.querySelector('.language-toggle');
const languageTarget = languageLink.getAttribute('href');
languageLink.addEventListener('click', () => {
  languageLink.href = languageTarget + window.location.hash;
});
const sections = document.querySelectorAll('main > section[id]');
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    nav.querySelectorAll('a').forEach(link => {
      if (link.hash === '#' + entry.target.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  });
}, {rootMargin: '-15% 0px -65% 0px'});
sections.forEach(section => observer.observe(section));

// Interactive 3D overview and one level of information technology subfields.
const viewport = document.querySelector('.map-viewport');
if (viewport) {
  const map = viewport.closest('.research-map');
  const svg = viewport.querySelector('svg');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fields = JSON.parse(map.dataset.mapFields);
  const topics = JSON.parse(map.dataset.mapTopics).map(([id, title], index) => ({
    id, title,
    color: ['#60e1c2', '#a9bdff', '#f2c580'][index],
  }));
  const backButton = map.querySelector('.map-back');
  const currentTitle = map.querySelector('.map-current');
  const legend = map.querySelector('.map-legend');
  const subfieldList = map.querySelector('.map-subfields');
  const ns = 'http://www.w3.org/2000/svg';
  const geometry = document.createElementNS(ns, 'g');
  let points = [], edges = [], rings = [];
  let nodeLayer, labelLayer, center;
  let currentField = null, overviewView = null;
  const initialRotation = {x: -.12, y: -.2, z: 0};
  let rotation = {...initialRotation}, target = {...rotation}, base = {...rotation};
  let zoom = 1, frame = null, drag = null, dragged = false;
  let autoRotate = !reducedMotion.matches, pointerOver = false, mapVisible = true;
  let lastFrame = null, resumeAt = 0, directionTime = 0;
  function randomVelocity() {
    const direction = {x: Math.random() * 2 - 1, y: Math.random() * 2 - 1, z: (Math.random() * 2 - 1) * .5};
    const length = Math.hypot(direction.x, direction.y, direction.z) || 1;
    const speed = 2 * (.022 + Math.random() * .016); // Double the original rotation speed.
    return Object.fromEntries(Object.entries(direction).map(([axis, value]) => [axis, value / length * speed]));
  }
  let velocity = randomVelocity(), nextVelocity = randomVelocity();
  function automaticMotionAllowed() {
    return autoRotate && !pointerOver && !drag && !map.querySelector(':focus-visible');
  }

  function element(tag, attrs, parent = geometry) {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    parent.append(node);
    return node;
  }
  function linesFor(text) {
    if (!text.includes(' ')) return [text];
    const lines = [''];
    for (const word of text.split(' ')) {
      const last = lines.length - 1;
      if (lines[last] && (lines[last] + ' ' + word).length > 18) lines.push(word);
      else lines[last] += (lines[last] ? ' ' : '') + word;
    }
    return lines;
  }
  function buildScene(field) {
    points = []; edges = []; rings = [];
    geometry.replaceChildren();
    const ringLayer = element('g', {fill: 'none', stroke: '#50768a', 'stroke-width': '.8', 'aria-hidden': 'true'});
    const edgeLayer = element('g', {fill: 'none', 'stroke-width': '1', 'aria-hidden': 'true'});
    nodeLayer = element('g', {'aria-hidden': 'true'});
    labelLayer = element('g', {});
    for (let plane = 0; plane < 3; plane++) {
      const ring = [];
      for (let i = 0; i <= 96; i++) {
        const angle = i / 96 * Math.PI * 2;
        const a = Math.cos(angle) * 174, b = Math.sin(angle) * 174;
        ring.push(plane === 0 ? [a, b, 0] : plane === 1 ? [a, 0, b] : [0, a, b]);
      }
      rings.push({points: ring, node: element('path', {opacity: '.65'}, ringLayer)});
    }
    const anchors = field ? fields[field.id].map((title, index, items) => {
      const angle = -Math.PI / 2 + index * Math.PI * 2 / items.length;
      return {title, color: field.color, position: [Math.cos(angle) * 148, Math.sin(angle) * 148, index % 2 ? -55 : 45]};
    }) : topics.map((topic, index) => ({...topic, position: [[-135, -65, 90], [105, -105, -50], [80, 125, 65]][index]}));
    anchors.forEach((anchor, group) => {
      points.push({...anchor, group, anchor: true});
      const count = field ? 6 : 16;
      for (let i = 0; i < count; i++) {
        const angle = i * 2.399963;
        const radius = field ? 16 + i * 3 : 24 + Math.sqrt(i / count) * 58;
        const satellite = [anchor.position[0] + Math.cos(angle) * radius,
          anchor.position[1] + Math.sin(angle) * radius * .7,
          anchor.position[2] + Math.sin(i * 1.7) * (field ? 24 : 65)];
        const fit = Math.min(1, 180 / Math.hypot(...satellite));
        points.push({position: satellite.map(value => value * fit), color: anchor.color, group});
      }
    });
    for (let a = 0; a < points.length; a++) {
      for (let b = a + 1; b < points.length; b++) {
        const first = points[a], second = points[b];
        const distance = Math.hypot(...first.position.map((n, i) => n - second.position[i]));
        if ((first.group === second.group && distance < 76) || (first.anchor && second.anchor)) {
          edges.push({a, b, node: element('line', {stroke: first.color}, edgeLayer)});
        }
      }
    }
    if (field) {
      center = element('g', {'aria-hidden': 'true'}, nodeLayer);
      element('circle', {cx: 260, cy: 210, r: 32, fill: '#142b3d', stroke: field.color, 'stroke-opacity': '.5'}, center);
      const label = element('text', {x: 260, y: 216, 'text-anchor': 'middle', fill: field.color, 'font-size': 17}, center);
      label.textContent = field.id.toUpperCase();
    }
    points.forEach(point => {
      point.node = element('circle', {fill: point.color}, nodeLayer);
      if (!point.anchor) return;
      point.halo = element('circle', {fill: 'none', stroke: point.color, 'stroke-width': '1.5', opacity: '.45'}, nodeLayer);
      const attrs = point.id ? {class: 'map-domain', 'data-map-field': point.id, role: 'button', tabindex: '0', 'aria-label': point.title} : {class: 'map-subfield-node', 'aria-hidden': 'true'};
      point.labelGroup = element('g', attrs, labelLayer);
      if (point.id) {
        point.hit = element('circle', {r: 34, fill: 'transparent'}, point.labelGroup);
        element('title', {}, point.labelGroup).textContent = point.title;
      }
      point.connector = element('line', {stroke: point.color, 'stroke-opacity': '.45', 'pointer-events': 'none'}, point.labelGroup);
      point.plate = element('rect', {class: 'map-label-plate', width: 156, rx: 6, fill: '#102638', stroke: point.color, 'stroke-opacity': '.5'}, point.labelGroup);
      const lines = linesFor(point.title);
      point.height = lines.length * 20 + 16;
      point.plate.setAttribute('height', point.height);
      point.label = element('text', {'text-anchor': 'middle', 'font-size': 16, 'font-weight': '500', fill: '#edf6fb', 'pointer-events': 'none'}, point.labelGroup);
      point.lines = lines.map(line => {
        const span = element('tspan', {}, point.label);
        span.textContent = line;
        return span;
      });
      if (field) {
        point.number = element('text', {'text-anchor': 'middle', 'font-size': 12, fill: '#fff', 'aria-hidden': 'true'}, nodeLayer);
        point.number.textContent = String(point.group + 1).padStart(2, '0');
      }
    });
  }
  function project([x, y, z]) {
    const x1 = x * Math.cos(rotation.y) + z * Math.sin(rotation.y);
    const z1 = z * Math.cos(rotation.y) - x * Math.sin(rotation.y);
    const y1 = y * Math.cos(rotation.x) - z1 * Math.sin(rotation.x);
    const z2 = z1 * Math.cos(rotation.x) + y * Math.sin(rotation.x);
    const x2 = x1 * Math.cos(rotation.z) - y1 * Math.sin(rotation.z);
    const y2 = x1 * Math.sin(rotation.z) + y1 * Math.cos(rotation.z);
    const scale = 650 / (650 + z2) * zoom * .86;
    return {x: 260 + x2 * scale, y: 210 + y2 * scale, depth: z2, scale};
  }
  function render(now = performance.now()) {
    frame = null;
    if (document.hidden || !mapVisible) { lastFrame = null; return; }
    // Use elapsed time so high refresh rates do not make the graph rotate faster.
    const elapsed = lastFrame === null ? 1 / 60 : Math.min((now - lastFrame) / 1000, .05);
    lastFrame = now;
    const automatic = automaticMotionAllowed();
    if (automatic && now >= resumeAt) {
      directionTime -= elapsed;
      if (directionTime <= 0) {
        nextVelocity = randomVelocity();
        directionTime = 8 + Math.random() * 8;
      }
      const blend = 1 - Math.exp(-elapsed / 3);
      for (const axis of ['x', 'y', 'z']) {
        velocity[axis] += (nextVelocity[axis] - velocity[axis]) * blend;
        base[axis] += velocity[axis] * elapsed;
        target[axis] = base[axis];
      }
    }
    const easing = reducedMotion.matches ? 1 : 1 - Math.exp(-elapsed * 12);
    for (const axis of ['x', 'y', 'z']) rotation[axis] += (target[axis] - rotation[axis]) * easing;
    const projected = points.map(point => project(point.position));
    rings.forEach(ring => {
      ring.node.setAttribute('d', ring.points.map((point, index) => {
        const p = project(point);
        return `${index ? 'L' : 'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`;
      }).join(' ') + 'Z');
    });
    edges.forEach(edge => {
      const a = projected[edge.a], b = projected[edge.b];
      for (const [key, value] of Object.entries({x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        opacity: Math.max(.1, .4 - (a.depth + b.depth) / 1400)})) edge.node.setAttribute(key, value);
    });
    points.map((point, i) => ({point, p: projected[i]})).sort((a, b) => b.p.depth - a.p.depth).forEach(({point, p}) => {
      point.node.setAttribute('cx', p.x);
      point.node.setAttribute('cy', p.y);
      point.node.setAttribute('r', (point.anchor ? (currentField ? 13 : 7) : 2.5) * p.scale);
      point.node.setAttribute('opacity', Math.max(.35, .9 - p.depth / 600));
      nodeLayer.append(point.node);
      if (point.anchor) {
        point.halo.setAttribute('cx', p.x);
        point.halo.setAttribute('cy', p.y);
        point.halo.setAttribute('r', (currentField ? 19 : 14) * p.scale);
        if (point.number) {
          point.number.setAttribute('x', p.x);
          point.number.setAttribute('y', p.y + 4);
          nodeLayer.append(point.number);
        }
      }
    });
    // Keep labels legible and within the graph, including at oblique angles.
    const occupied = [];
    let labelsMoving = false;
    points.forEach((point, index) => {
      if (!point.anchor) return;
      const p = projected[index];
      const x = Math.max(8, Math.min(356, p.x - 78));
      const direction = p.y < 210 ? -1 : 1;
      const candidates = [40, -40, 90, -90, 145, -145, 190, -190].map(offset => ({
        x, y: Math.max(8, Math.min(412 - point.height, p.y + offset * direction - point.height / 2)),
        width: 156, height: point.height,
      }));
      const destination = candidates.find(candidate => !occupied.some(other => candidate.x < other.x + other.width + 6 && candidate.x + candidate.width + 6 > other.x && candidate.y < other.y + other.height + 6 && candidate.y + candidate.height + 6 > other.y)) || candidates[0];
      occupied.push(destination);
      // Ease label repositioning too, so crossing the equator never causes a jump.
      const box = point.labelPosition || {...destination};
      const labelEasing = reducedMotion.matches ? 1 : 1 - Math.exp(-elapsed * 8);
      box.x += (destination.x - box.x) * labelEasing;
      box.y += (destination.y - box.y) * labelEasing;
      point.labelPosition = box;
      labelsMoving ||= Math.abs(destination.x - box.x) + Math.abs(destination.y - box.y) > .1;
      if (point.hit) { point.hit.setAttribute('cx', p.x); point.hit.setAttribute('cy', p.y); }
      point.plate.setAttribute('x', box.x); point.plate.setAttribute('y', box.y);
      for (const [key, value] of Object.entries({x1: p.x, y1: p.y, x2: box.x + 78, y2: box.y + box.height / 2})) point.connector.setAttribute(key, value);
      point.lines.forEach((line, i) => {
        line.setAttribute('x', box.x + 78);
        line.setAttribute('y', box.y + 22 + i * 20);
      });
    });
    if (automatic || labelsMoving || ['x', 'y', 'z'].some(axis => Math.abs(target[axis] - rotation[axis]) > .001)) schedule();
  }
  function schedule() { if (frame === null) frame = requestAnimationFrame(render); }
  function showField(id) {
    const field = topics.find(topic => topic.id === id) || null;
    if (field && currentField === null) overviewView = {rotation: {...rotation}, base: {...target}, zoom};
    const previous = currentField;
    currentField = field?.id || null;
    map.dataset.mapLevel = field ? 'subfields' : 'overview';
    map.dataset.mapField = currentField || '';
    legend.hidden = Boolean(field);
    subfieldList.hidden = !field;
    backButton.hidden = !field;
    currentTitle.textContent = field ? field.title + ' / ' + map.dataset.mapSubfields : map.dataset.mapOverview;
    svg.querySelector('title').textContent = currentTitle.textContent;
    viewport.setAttribute('aria-label', currentTitle.textContent);
    subfieldList.replaceChildren();
    if (field) {
      fields[field.id].forEach((title, index) => {
        const item = document.createElement('li');
        const number = document.createElement('span');
        number.className = 'map-subfield-number';
        number.textContent = String(index + 1).padStart(2, '0');
        const label = document.createElement('span');
        label.textContent = title;
        item.append(number, label);
        subfieldList.append(item);
      });
    }
    base = field || !overviewView ? {...initialRotation} : {...overviewView.base};
    rotation = field || !overviewView ? {...initialRotation} : {...overviewView.rotation};
    target = {...base};
    zoom = field || !overviewView ? 1 : overviewView.zoom;
    lastFrame = null;
    resumeAt = performance.now() + 1200;
    buildScene(field);
    // Lay out the new scene before moving focus to its navigation.
    if (frame !== null) cancelAnimationFrame(frame);
    render();
    if (field) backButton.focus({preventScroll: true});
    else if (previous) svg.querySelector('.map-domain[data-map-field="' + previous + '"]').focus({preventScroll: true});
  }
  function action(kind) {
    if (kind === 'reset') {
      base = {...initialRotation}; target = {...base}; zoom = 1;
    } else zoom = Math.max(.7, Math.min(1.2, zoom + (kind === 'zoom-in' ? .1 : -.1)));
    schedule();
  }
  viewport.addEventListener('pointerdown', event => {
    if (event.button !== 0 || !event.isPrimary) return;
    dragged = false;
    drag = {id: event.pointerId, x: event.clientX, y: event.clientY, start: {...target}};
  });
  viewport.addEventListener('pointermove', event => {
    if (drag && drag.id === event.pointerId) {
      if (!dragged && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 7) return;
      dragged = true;
      viewport.setPointerCapture(event.pointerId);
      viewport.classList.add('is-dragging');
      target.y = drag.start.y + (event.clientX - drag.x) * .008;
      target.x = drag.start.x + (event.clientY - drag.y) * .008;
      base = {...target};
    } else if (event.pointerType === 'mouse' && !reducedMotion.matches && !event.target.closest('.map-domain')) {
      const rect = viewport.getBoundingClientRect();
      target = {x: base.x - ((event.clientY - rect.top) / rect.height - .5) * .5,
        y: base.y + ((event.clientX - rect.left) / rect.width - .5) * .65, z: base.z};
    } else return;
    schedule();
  });
  function finishDrag(event) {
    if (!drag || drag.id !== event.pointerId) return;
    drag = null;
    viewport.classList.remove('is-dragging');
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
  }
  viewport.addEventListener('pointerup', finishDrag);
  viewport.addEventListener('pointercancel', event => { dragged = true; finishDrag(event); });
  viewport.addEventListener('lostpointercapture', finishDrag);
  viewport.addEventListener('pointerleave', event => {
    if (drag && !dragged) finishDrag(event);
    if (!drag) { target = {...base}; schedule(); }
  });
  viewport.addEventListener('click', event => {
    const domain = event.target.closest('.map-domain');
    if (domain && !dragged) showField(domain.dataset.mapField);
  });
  viewport.addEventListener('keydown', event => {
    const domain = event.target.closest('.map-domain');
    if (domain && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault(); showField(domain.dataset.mapField); return;
    }
    const directions = {ArrowLeft: ['y', -.25], ArrowRight: ['y', .25], ArrowUp: ['x', -.25], ArrowDown: ['x', .25]};
    if (directions[event.key]) {
      const [axis, amount] = directions[event.key];
      target[axis] += amount; base = {...target}; schedule();
    } else if (event.key === 'Home') action('reset');
    else if (event.key === '+' || event.key === '=') action('zoom-in');
    else if (event.key === '-') action('zoom-out');
    else if (event.key === ' ') {
      autoRotate = !autoRotate;
      lastFrame = null;
      schedule();
    }
    else return;
    event.preventDefault();
  });
  map.addEventListener('keydown', event => {
    if (event.key === 'Escape' && currentField) { event.preventDefault(); showField(null); }
  });
  map.addEventListener('pointerenter', event => {
    if (event.pointerType === 'touch') return;
    pointerOver = true;
    base = {...rotation}; target = {...rotation};
    schedule();
  });
  map.addEventListener('pointerleave', event => {
    if (event.pointerType === 'touch') return;
    pointerOver = false;
    resumeAt = performance.now() + 1200;
    lastFrame = null;
    schedule();
  });
  map.addEventListener('pointerup', () => {
    resumeAt = performance.now() + 1500;
    schedule();
  });
  map.addEventListener('focusin', () => {
    if (map.querySelector(':focus-visible')) { base = {...rotation}; target = {...rotation}; }
    schedule();
  });
  map.addEventListener('focusout', () => {
    resumeAt = performance.now() + 1200;
    schedule();
  });
  reducedMotion.addEventListener('change', () => {
    autoRotate = !reducedMotion.matches;
    lastFrame = null;
    schedule();
  });
  document.addEventListener('visibilitychange', () => { lastFrame = null; schedule(); });
  const mapObserver = new IntersectionObserver(entries => {
    mapVisible = entries[0].isIntersecting;
    lastFrame = null;
    schedule();
  });
  mapObserver.observe(viewport);
  backButton.addEventListener('click', () => showField(null));
  svg.querySelector('.map-fallback').remove();
  svg.append(geometry);
  map.querySelector('.map-navigation').hidden = false;
  showField(null);
}

// Flask pages check for edited Markdown; static exports make no API requests.
if (document.body.dataset.mode === 'server') {
  setInterval(async () => {
    if (document.hidden || nav.classList.contains('is-open') || document.activeElement?.closest('.map-viewport')) return;
    try {
      const response = await fetch('/api/content/version', {cache: 'no-store'});
      if (response.ok && (await response.json()).version !== document.body.dataset.version) location.reload();
    } catch (_) { /* Preserve the current page during a temporary outage. */ }
  }, 30000);
}
