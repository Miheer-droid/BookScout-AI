/* ============================================================
   BookScout AI — Frontend Application
   ============================================================ */

(() => {
  'use strict';

  // ─── DOM References ──────────────────────────────────────────
  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  const dom = {
    // States
    landing:    $('#landing'),
    processing: $('#processing'),
    results:    $('#results'),

    // Landing
    form:       $('#research-form'),
    input:      $('#query-input'),
    researchBtn: $('#research-btn'),
    surpriseBtn: $('#surprise-btn'),

    // Processing
    processingQuery: $('#processing-query'),
    progressFill:    $('#progress-fill'),
    progressLabel:   $('#progress-label'),
    timeline:        $('#workflow-timeline'),

    // Results
    resultsQuery:     $('#results-query'),
    confidenceFill:   $('#confidence-fill'),
    confidenceLabel:  $('#confidence-label'),
    topPickTitle:     $('#top-pick-title'),
    topPickAuthor:    $('#top-pick-author'),
    topPickDesc:      $('#top-pick-description'),
    topPickReasons:   $('#top-pick-reasons'),
    topPickReviews:   $('#top-pick-reviews'),
    topPickPricing:   $('#top-pick-pricing'),
    topPickDifficulty: $('#top-pick-difficulty'),
    topPickSources:   $('#top-pick-sources'),
    topPickScore:     $('#top-pick-score'),
    scoreRingFill:    $('#score-ring-fill'),
    scoreRingValue:   $('#score-ring-value'),
    alternativesSection: $('#alternatives-section'),
    alternativesGrid: $('#alternatives-grid'),
    reasoningCard:    $('#reasoning-card'),
    reasoningText:    $('#reasoning-text'),
    errorCard:        $('#error-card'),
    errorText:        $('#error-text'),
    startOverBtn:     $('#start-over-btn'),
  };

  // ─── Agent → Step Mapping ────────────────────────────────────
  const AGENT_ORDER = [
    'understanding',
    'planning',
    'search',
    'reviews',
    'pricing',
    'analysis',
    'recommendation',
  ];

  const AGENT_LABELS = {
    understanding:  'Understanding your interests',
    planning:       'Planning research strategy',
    search:         'Finding relevant books',
    reviews:        'Researching reviews & ratings',
    pricing:        'Comparing prices',
    analysis:       'Analyzing reading difficulty',
    recommendation: 'Ranking recommendations',
  };

  let currentQuery = '';
  let completedCount = 0;

  // ─── State Transitions ──────────────────────────────────────
  function switchState(stateName) {
    [dom.landing, dom.processing, dom.results].forEach(el => {
      el.classList.remove('state--active');
    });

    const target = stateName === 'landing'    ? dom.landing
                 : stateName === 'processing' ? dom.processing
                 : dom.results;

    // Small delay so CSS transition plays
    requestAnimationFrame(() => {
      target.classList.add('state--active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ─── Reset Workflow ──────────────────────────────────────────
  function resetWorkflow() {
    completedCount = 0;
    dom.progressFill.style.width = '0%';
    dom.progressLabel.textContent = 'Starting...';

    $$('.workflow-step', dom.timeline).forEach(step => {
      step.classList.remove('workflow-step--visible', 'workflow-step--active', 'workflow-step--completed');
      const msg = $('.workflow-step__message', step);
      if (msg) msg.textContent = '';
      const detail = $('.workflow-step__detail', step);
      if (detail) detail.innerHTML = '';
    });
  }

  // ─── Animate Steps In ────────────────────────────────────────
  function revealSteps() {
    const steps = $$('.workflow-step', dom.timeline);
    steps.forEach((step, i) => {
      setTimeout(() => {
        step.classList.add('workflow-step--visible');
      }, i * 120);
    });
  }

  // ─── Handle Agent Update ─────────────────────────────────────
  function handleAgentUpdate(event) {
    const { agent, status, message, data } = event;

    // Find the matching step element
    const stepEl = $(`.workflow-step[data-agent="${agent}"]`, dom.timeline);
    if (!stepEl) return;

    const msgEl = $('.workflow-step__message', stepEl);

    if (status === 'started' || status === 'working') {
      // Remove active from all, set this one active
      $$('.workflow-step--active', dom.timeline).forEach(el =>
        el.classList.remove('workflow-step--active')
      );
      stepEl.classList.add('workflow-step--active');
      if (msgEl && message) msgEl.textContent = message;
      if (data) renderStepDetail(agent, data);

      // Update progress label
      const label = AGENT_LABELS[agent] || agent;
      dom.progressLabel.textContent = message || label;
    }

    if (status === 'progress') {
      // Per-book progress update — doesn't change active/completed state,
      // just refreshes the live book list and message text.
      if (msgEl && message) msgEl.textContent = message;
      if (data) renderStepDetail(agent, data);
    }

    if (status === 'completed') {
      stepEl.classList.remove('workflow-step--active');
      stepEl.classList.add('workflow-step--completed');
      if (msgEl && message) msgEl.textContent = message;

      if (data) renderStepDetail(agent, data);

      completedCount++;
      const pct = Math.round((completedCount / AGENT_ORDER.length) * 100);
      dom.progressFill.style.width = pct + '%';
      dom.progressLabel.textContent = completedCount === AGENT_ORDER.length
        ? '✅ Done!'
        : `${pct}% complete`;
    }

    if (status === 'error') {
      stepEl.classList.remove('workflow-step--active');
      if (msgEl && message) {
        msgEl.textContent = '⚠️ ' + message;
        msgEl.style.color = '#EF4444';
      }
    }
  }

  // ─── Render Real Step Detail (Understanding / Planning / Search) ──
  function renderStepDetail(agent, data) {
    const el = document.getElementById(`detail-${agent}`);
    if (!el) return;
    el.innerHTML = '';

    if (agent === 'understanding' && data.intent) {
      const intent = data.intent;
      if (intent.goal) {
        el.appendChild(makeChip(intent.goal, 'detail-chip--goal', '🎯'));
      }
      (intent.interests || []).forEach(v => el.appendChild(makeChip(v, '', '📖')));
      (intent.previous_books || []).forEach(v => el.appendChild(makeChip(v, '', '📗')));
      (intent.likes || []).forEach(v => el.appendChild(makeChip(v, '', '👍')));
      (intent.dislikes || []).forEach(v => el.appendChild(makeChip(v, '', '👎')));
      if (intent.reading_level && intent.reading_level !== 'unknown') {
        el.appendChild(makeChip(intent.reading_level, '', '🎓'));
      }
    }

    if (agent === 'planning' && data.plan) {
      (data.plan.search_queries || []).forEach(q =>
        el.appendChild(makeChip(q, 'detail-chip--query', '🔎'))
      );
    }

    if (agent === 'search' && data.books) {
      data.books.forEach(b => {
        const label = b.author ? `${b.title} — ${b.author}` : b.title;
        el.appendChild(makeChip(label, 'detail-chip--book', '📘'));
      });
    }

    if ((agent === 'reviews' || agent === 'pricing' || agent === 'analysis') && data.books) {
      const list = document.createElement('div');
      list.className = 'detail-book-list';
      data.books.forEach(b => {
        const row = document.createElement('div');
        const done = b.status === 'done';
        row.className = 'detail-book-row' + (done ? ' detail-book-row--done' : '');
        const dot = document.createElement('span');
        dot.className = 'detail-book-row__dot';
        const label = document.createElement('span');
        label.textContent = done ? `${b.title} ✓` : `${b.title}…`;
        row.appendChild(dot);
        row.appendChild(label);
        list.appendChild(row);
      });
      el.innerHTML = '';
      el.appendChild(list);
    }
  }

  function makeChip(text, extraClass, icon) {
    const chip = document.createElement('span');
    chip.className = `detail-chip ${extraClass}`.trim();
    chip.textContent = icon ? `${icon} ${text}` : text;
    return chip;
  }


  // ─── Render Results ──────────────────────────────────────────
  function renderResults(data) {
    const { top_pick, alternatives, overall_confidence, reasoning } = data;

    // Query echo
    dom.resultsQuery.textContent = `"${currentQuery}"`;

    // Confidence
    const confMap = { high: 90, medium: 65, low: 35 };
    const confPct = confMap[overall_confidence] || 70;
    dom.confidenceFill.style.width = confPct + '%';
    dom.confidenceLabel.textContent = `${overall_confidence?.toUpperCase() || 'MEDIUM'} confidence`;
    dom.confidenceLabel.style.color =
      confPct >= 80 ? '#22C55E' : confPct >= 50 ? '#F59E0B' : '#EF4444';

    // Top pick
    if (top_pick) {
      renderTopPick(top_pick);
    }

    // Alternatives
    dom.alternativesGrid.innerHTML = '';
    if (alternatives && alternatives.length > 0) {
      dom.alternativesSection.style.display = 'block';
      alternatives.forEach((alt, i) => renderAltCard(alt, i));
    } else {
      dom.alternativesSection.style.display = 'none';
    }

    // Reasoning
    if (reasoning) {
      dom.reasoningCard.style.display = 'block';
      dom.reasoningText.textContent = reasoning;
    } else {
      dom.reasoningCard.style.display = 'none';
    }

    // Switch to results
    setTimeout(() => switchState('results'), 600);
  }

  // ─── Render Top Pick ─────────────────────────────────────────
  function renderTopPick(pick) {
    const book = pick.book || {};
    const reviews = pick.reviews || {};
    const pricing = pick.pricing || {};
    const analysis = pick.analysis || {};
    const reasons = pick.match_reasons || [];
    const score = pick.score || 0;

    dom.topPickTitle.textContent = book.title || 'Untitled';
    dom.topPickAuthor.textContent = book.author ? `by ${book.author}` : '';
    dom.topPickDesc.textContent = book.description || '';

    // Match reasons
    const existingReasons = $$('.reason-badge', dom.topPickReasons);
    existingReasons.forEach(el => el.remove());
    reasons.forEach(reason => {
      const badge = document.createElement('div');
      badge.className = 'reason-badge';
      badge.innerHTML = `<span class="reason-badge__icon">✅</span> ${escapeHtml(reason)}`;
      dom.topPickReasons.appendChild(badge);
    });

    // Reviews
    const reviewsBody = $('.detail-card__body', dom.topPickReviews);
    reviewsBody.innerHTML = '';
    if (reviews.average_rating) {
      reviewsBody.innerHTML += `<p><strong>${reviews.average_rating}★</strong> average${reviews.total_reviews ? ` (${reviews.total_reviews} reviews)` : ''}</p>`;
    }
    if (reviews.praise && reviews.praise.length) {
      reviews.praise.forEach(p => {
        reviewsBody.innerHTML += `<p class="praise">👍 ${escapeHtml(p)}</p>`;
      });
    }
    if (reviews.complaints && reviews.complaints.length) {
      reviews.complaints.forEach(c => {
        reviewsBody.innerHTML += `<p class="complaint">👎 ${escapeHtml(c)}</p>`;
      });
    }
    if (!reviewsBody.innerHTML) {
      reviewsBody.innerHTML = '<p>No review data available</p>';
    }

    // Pricing
    const pricingBody = $('.detail-card__body', dom.topPickPricing);
    pricingBody.innerHTML = '';
    if (pricing.formats) {
      Object.entries(pricing.formats).forEach(([fmt, price]) => {
        pricingBody.innerHTML += `<span class="price-tag">${escapeHtml(fmt)}: ${escapeHtml(String(price))}</span> `;
      });
    } else if (pricing.price) {
      pricingBody.innerHTML = `<span class="price-tag">${escapeHtml(String(pricing.price))}</span>`;
    } else if (typeof pricing === 'string') {
      pricingBody.innerHTML = `<p>${escapeHtml(pricing)}</p>`;
    } else {
      pricingBody.innerHTML = '<p>No pricing data available</p>';
    }

    // Difficulty
    const diffBody = $('.detail-card__body', dom.topPickDifficulty);
    const level = analysis.difficulty_level || analysis.level || 'Unknown';
    const levelLower = level.toLowerCase();
    const diffClass = levelLower.includes('easy') || levelLower.includes('beginner')
      ? 'easy'
      : levelLower.includes('hard') || levelLower.includes('advanced')
        ? 'hard'
        : 'medium';
    diffBody.innerHTML = `<span class="difficulty-badge difficulty-badge--${diffClass}">${escapeHtml(level)}</span>`;
    if (analysis.page_count) {
      diffBody.innerHTML += `<p style="margin-top:8px">${analysis.page_count} pages</p>`;
    }
    if (analysis.summary) {
      diffBody.innerHTML += `<p style="margin-top:4px;color:var(--text-muted);font-size:0.85rem">${escapeHtml(analysis.summary)}</p>`;
    }

    // Sources
    const existingSources = $$('.sources-list', dom.topPickSources);
    existingSources.forEach(el => el.remove());
    const sources = pick.sources || book.sources || [];
    if (sources.length) {
      const list = document.createElement('div');
      list.className = 'sources-list';
      sources.forEach(src => {
        const badge = document.createElement('span');
        badge.className = 'source-badge';
        badge.textContent = src;
        list.appendChild(badge);
      });
      dom.topPickSources.appendChild(list);
    }

    // Score ring
    dom.scoreRingValue.textContent = Math.round(score);
    const circumference = 2 * Math.PI * 52; // r=52
    const offset = circumference - (score / 100) * circumference;
    // Animate after a short delay
    setTimeout(() => {
      dom.scoreRingFill.style.strokeDashoffset = offset;
    }, 400);
  }

  // ─── Render Alternative Card ─────────────────────────────────
  function renderAltCard(alt, index) {
    const book = alt.book || {};
    const reviews = alt.reviews || {};
    const pricing = alt.pricing || {};
    const analysis = alt.analysis || {};
    const score = alt.score || 0;
    const reasons = alt.match_reasons || alt.why_not || [];

    const card = document.createElement('div');
    card.className = 'alt-card';
    card.style.animationDelay = `${index * 0.1}s`;

    const rank = alt.rank || (index + 2);
    const level = analysis.difficulty_level || analysis.level || '';
    const levelLower = level.toLowerCase();
    const diffClass = levelLower.includes('easy') || levelLower.includes('beginner')
      ? 'easy'
      : levelLower.includes('hard') || levelLower.includes('advanced')
        ? 'hard'
        : 'medium';

    // Build reviews summary text
    let reviewSummary = '';
    if (reviews.average_rating) {
      reviewSummary = `${reviews.average_rating}★`;
      if (reviews.total_reviews) reviewSummary += ` (${reviews.total_reviews} reviews)`;
    }

    // Build pricing text
    let pricingHtml = '';
    if (pricing.formats) {
      Object.entries(pricing.formats).forEach(([fmt, price]) => {
        pricingHtml += `<span class="price-tag" style="font-size:0.78rem">${escapeHtml(fmt)}: ${escapeHtml(String(price))}</span> `;
      });
    } else if (pricing.price) {
      pricingHtml = `<span class="price-tag" style="font-size:0.78rem">${escapeHtml(String(pricing.price))}</span>`;
    }

    // Reasons list for "Why not this?"
    let reasonsHtml = '';
    if (reasons.length) {
      reasonsHtml = reasons.map(r => `<p>• ${escapeHtml(r)}</p>`).join('');
    } else {
      reasonsHtml = '<p>Ranked lower based on overall match to your criteria.</p>';
    }

    card.innerHTML = `
      <div class="alt-card__rank">#${rank} Pick</div>
      <div class="alt-card__content">
        <h4 class="alt-card__title">${escapeHtml(book.title || 'Untitled')}</h4>
        <p class="alt-card__author">${book.author ? 'by ' + escapeHtml(book.author) : ''}</p>
        <p class="alt-card__description">${escapeHtml(book.description || '')}</p>
        <div class="alt-card__meta">
          ${level ? `<span class="difficulty-badge difficulty-badge--${diffClass}" style="font-size:0.78rem;padding:3px 10px">${escapeHtml(level)}</span>` : ''}
          <span class="alt-card__score">⭐ ${Math.round(score)}</span>
        </div>
        ${reviewSummary ? `<div class="alt-card__reviews-summary">${escapeHtml(reviewSummary)}</div>` : ''}
        ${pricingHtml ? `<div class="alt-card__pricing-info">${pricingHtml}</div>` : ''}
        <button class="alt-card__why-not-btn" aria-expanded="false">
          <span>Why not this?</span>
          <span class="alt-card__chevron">▾</span>
        </button>
        <div class="alt-card__why-not-body">
          <div class="alt-card__reasons-list">${reasonsHtml}</div>
        </div>
      </div>
    `;

    // Toggle handler
    const btn = $('.alt-card__why-not-btn', card);
    const body = $('.alt-card__why-not-body', card);
    btn.addEventListener('click', () => {
      const isOpen = body.classList.contains('open');
      btn.classList.toggle('open');
      body.classList.toggle('open');
      btn.setAttribute('aria-expanded', !isOpen);
    });

    dom.alternativesGrid.appendChild(card);
  }

  // ─── Pill Selectors (Level / Goal) ───────────────────────────
  function setupPillGroup(groupId) {
    const group = document.getElementById(groupId);
    if (!group) return;
    $$('.pill-option', group).forEach(btn => {
      btn.addEventListener('click', () => {
        const alreadySelected = btn.classList.contains('pill-option--selected');
        $$('.pill-option', group).forEach(b => b.classList.remove('pill-option--selected'));
        if (!alreadySelected) btn.classList.add('pill-option--selected');
      });
    });
  }

  function getSelectedPill(groupId) {
    const group = document.getElementById(groupId);
    if (!group) return null;
    const selected = $('.pill-option--selected', group);
    return selected ? selected.dataset.value : null;
  }

  function selectPill(groupId, value) {
    const group = document.getElementById(groupId);
    if (!group) return;
    $$('.pill-option', group).forEach(btn => {
      btn.classList.toggle('pill-option--selected', btn.dataset.value === value);
    });
  }

  function clearPills(groupId) {
    const group = document.getElementById(groupId);
    if (!group) return;
    $$('.pill-option', group).forEach(btn => btn.classList.remove('pill-option--selected'));
  }

  // Maps the friendly pill label to the exact schema-compatible token, so
  // the backend receives a deterministic value and never has to guess or
  // interpret free text for reading_level.
  const LEVEL_TAG_VALUE = {
    'Complete beginner': 'beginner',
    'Some basics': 'beginner',
    'Comfortable': 'intermediate',
    'Advanced': 'advanced',
  };

  function buildTaggedQuery(rawQuery) {
    let query = rawQuery.trim();
    const level = getSelectedPill('level-group');
    const goal = getSelectedPill('goal-group');
    if (level) query += ` [Reading level: ${LEVEL_TAG_VALUE[level] || level}]`;
    if (goal) query += ` [Goal: ${goal}]`;
    return query;
  }

  // ─── Surprise Me ─────────────────────────────────────────────
  const SURPRISE_PICKS = [
    { query: 'Books about wizards who are surprisingly bad at their jobs', level: 'Some basics', goal: 'Just for fun' },
    { query: 'The history of tea and how it shaped empires', level: 'Complete beginner', goal: 'Learn from scratch' },
    { query: 'Mind-bending books about the nature of time', level: 'Comfortable', goal: 'Go deeper' },
    { query: 'Cozy mystery novels set in small towns', level: 'Some basics', goal: 'Just for fun' },
    { query: 'How ancient civilizations built things without modern tools', level: 'Complete beginner', goal: 'Learn from scratch' },
    { query: 'Books that explain how the stock market actually works', level: 'Complete beginner', goal: 'Learn from scratch' },
    { query: 'Philosophy books that won\u2019t make me feel dumb', level: 'Some basics', goal: 'Go deeper' },
    { query: 'Strange true stories about deep sea creatures', level: 'Comfortable', goal: 'Just for fun' },
    { query: 'Books on how to negotiate anything', level: 'Some basics', goal: 'Reference material' },
    { query: 'Epic fantasy series with morally gray characters', level: 'Advanced', goal: 'Just for fun' },
    { query: 'Practical guides to growing vegetables in a small backyard', level: 'Complete beginner', goal: 'Reference material' },
    { query: 'The science of why we dream', level: 'Comfortable', goal: 'Go deeper' },
  ];

  function surpriseMe() {
    const pick = SURPRISE_PICKS[Math.floor(Math.random() * SURPRISE_PICKS.length)];
    dom.input.value = pick.query;
    dom.input.style.height = 'auto';
    dom.input.style.height = Math.min(dom.input.scrollHeight, 200) + 'px';
    selectPill('level-group', pick.level);
    selectPill('goal-group', pick.goal);
    dom.input.focus();
    dom.input.style.borderColor = 'var(--brass)';
    setTimeout(() => { dom.input.style.borderColor = ''; }, 1000);
  }

  // ─── Start Research ──────────────────────────────────────────
  async function startResearch(rawQuery) {
    const taggedQuery = buildTaggedQuery(rawQuery);
    currentQuery = rawQuery.trim();
    if (!currentQuery) return;

    // Switch to processing
    resetWorkflow();
    dom.processingQuery.textContent = `"${currentQuery}"`;
    switchState('processing');

    // Reveal steps with stagger
    setTimeout(revealSteps, 300);

    try {
      const response = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: taggedQuery }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalData = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;

          try {
            const data = JSON.parse(trimmed.slice(6));
            handleAgentUpdate(data);

            // Check for final result
            if (data.agent === 'recommendation' && data.status === 'completed' && data.data) {
              finalData = data.data;
            }
          } catch (parseErr) {
            console.warn('Failed to parse SSE line:', trimmed, parseErr);
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim().startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.trim().slice(6));
          handleAgentUpdate(data);
          if (data.agent === 'recommendation' && data.status === 'completed' && data.data) {
            finalData = data.data;
          }
        } catch (e) {
          // ignore
        }
      }

      if (finalData) {
        renderResults(finalData);
      } else {
        showError('No recommendations were returned. The AI may have encountered an issue processing your request.');
      }

    } catch (err) {
      console.error('Research failed:', err);
      showError(err.message || 'An unexpected error occurred. Please try again.');
    }
  }

  // ─── Show Error ──────────────────────────────────────────────
  function showError(message) {
    dom.errorText.textContent = message;
    dom.errorCard.style.display = 'block';
    dom.reasoningCard.style.display = 'none';
    dom.alternativesSection.style.display = 'none';

    // Hide top-pick content but keep results visible with error
    $('#top-pick').style.display = 'none';
    $('#confidence-meter').style.display = 'none';

    dom.resultsQuery.textContent = `"${currentQuery}"`;
    switchState('results');
  }

  // ─── Start Over ──────────────────────────────────────────────
  function startOver() {
    // Reset all results
    dom.errorCard.style.display = 'none';
    $('#top-pick').style.display = 'block';
    $('#confidence-meter').style.display = 'flex';
    dom.alternativesSection.style.display = 'block';
    dom.reasoningCard.style.display = 'block';
    dom.alternativesGrid.innerHTML = '';
    dom.scoreRingFill.style.strokeDashoffset = 326.7;
    dom.input.value = '';
    clearPills('level-group');
    clearPills('goal-group');

    switchState('landing');

    // Focus input after transition
    setTimeout(() => dom.input.focus(), 500);
  }

  // ─── Helpers ─────────────────────────────────────────────────
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ─── Event Listeners ────────────────────────────────────────
  dom.form.addEventListener('submit', (e) => {
    e.preventDefault();
    startResearch(dom.input.value);
  });

  dom.startOverBtn.addEventListener('click', startOver);

  // Level / Goal pill selectors
  setupPillGroup('level-group');
  setupPillGroup('goal-group');

  // Surprise me
  if (dom.surpriseBtn) {
    dom.surpriseBtn.addEventListener('click', surpriseMe);
  }

  // Example chips — only ones with a data-query (excludes the surprise
  // button, which shares the same visual class but has its own handler)
  $$('.example-chip[data-query]').forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.dataset.query;
      dom.input.value = query;
      dom.input.focus();
      // Subtle visual feedback
      dom.input.style.borderColor = 'var(--amber)';
      setTimeout(() => { dom.input.style.borderColor = ''; }, 1000);
    });
  });

  // Auto-resize textarea
  dom.input.addEventListener('input', () => {
    dom.input.style.height = 'auto';
    dom.input.style.height = Math.min(dom.input.scrollHeight, 200) + 'px';
  });

  // Keyboard shortcut: Ctrl+Enter to submit
  dom.input.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      dom.form.dispatchEvent(new Event('submit'));
    }
  });

})();
