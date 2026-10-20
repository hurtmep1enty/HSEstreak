/*
  Небольшой скрипт для удобства. Сайт работает и без него (формы отправляются обычным образом),
  а скрипт добавляет:
    * переключение светлой/тёмной темы и акцентного цвета (запоминается в браузере);
    * мгновенную отметку привычки без перезагрузки страницы и конфетти;
    * предпросмотр цвета в форме привычки и «свой цвет»;
    * кнопки быстрого выбора дней недели;
    * определение часового пояса при регистрации.
*/
(function () {
  'use strict';
  var root = document.documentElement;

  /* ---------- хранилище в браузере (может быть недоступно, поэтому try/catch) ---------- */
  function save(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* ничего */ } }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

  /* ---------- тема и акцент ---------- */
  function systemDark() { return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches; }

  function applyTheme(mode) {
    var real = (!mode || mode === 'auto') ? (systemDark() ? 'dark' : 'light') : mode;
    root.setAttribute('data-theme', real);
  }

  function applyAccent(name) {
    if (name && name !== 'green') { root.setAttribute('data-accent', name); }
    else { root.removeAttribute('data-accent'); }
  }

  function markSettings() {
    var mode = load('theme') || 'auto';
    var accent = load('accent') || 'green';
    document.querySelectorAll('[data-theme-set]').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-theme-set') === mode);
    });
    document.querySelectorAll('[data-accent-set]').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-accent-set') === accent);
    });
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-theme-set]');
    if (t) {
      save('theme', t.getAttribute('data-theme-set'));
      applyTheme(t.getAttribute('data-theme-set'));
      markSettings();
      return;
    }
    var a = e.target.closest('[data-accent-set]');
    if (a) {
      save('accent', a.getAttribute('data-accent-set'));
      applyAccent(a.getAttribute('data-accent-set'));
      markSettings();
      return;
    }
    if (e.target.closest('#theme-toggle')) {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      save('theme', next);
      applyTheme(next);
      markSettings();
      return;
    }
    // Кнопки «каждый день / будни / выходные» в форме привычки
    var preset = e.target.closest('[data-days]');
    if (preset) {
      var days = preset.getAttribute('data-days').split(',');
      var form = preset.closest('form');
      form.querySelectorAll('input[name="days"]').forEach(function (box) {
        box.checked = days.indexOf(box.value) !== -1;
      });
    }
  });

  // Если тема «как в системе», следим за её сменой
  if (window.matchMedia) {
    var mq = matchMedia('(prefers-color-scheme: dark)');
    var onSystemChange = function () { if ((load('theme') || 'auto') === 'auto') { applyTheme('auto'); } };
    if (mq.addEventListener) { mq.addEventListener('change', onSystemChange); }
  }

  /* ---------- форма привычки: предпросмотр цвета и «свой цвет» ---------- */
  document.addEventListener('change', function (e) {
    var form = e.target.closest('.habit-form');
    if (form && e.target.name === 'color') { form.style.setProperty('--hc', e.target.value); }
  });

  document.addEventListener('input', function (e) {
    if (!e.target.matches('.sw.custom input[type="color"]')) { return; }
    var label = e.target.closest('.sw');
    var radio = label.querySelector('input[type="radio"]');
    var dot = label.querySelector('span');
    radio.value = e.target.value;          // сервер получит этот цвет, как обычный выбранный
    radio.checked = true;
    dot.style.background = e.target.value;
    dot.style.setProperty('--sw', e.target.value);
    e.target.closest('.habit-form').style.setProperty('--hc', e.target.value);
  });

  /* ---------- конфетти ---------- */
  function confetti(origin, color, count) {
    if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) { return; }
    var rect = origin ? origin.getBoundingClientRect()
                      : { left: innerWidth / 2, top: innerHeight / 3, width: 0, height: 0 };
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var colors = [color || '#43a047', '#ffd54f', '#ef5350', '#42a5f5', '#ab47bc', '#66bb6a'];
    var n = count || 26;
    for (var i = 0; i < n; i++) {
      var piece = document.createElement('i');
      var angle = Math.random() * Math.PI * 2;
      var dist = 50 + Math.random() * (n > 40 ? 240 : 120);
      piece.className = 'confetti';
      piece.style.left = cx + 'px';
      piece.style.top = cy + 'px';
      piece.style.background = colors[i % colors.length];
      piece.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
      piece.style.setProperty('--dy', Math.sin(angle) * dist + 50 + 'px');   // +50: конфетти немного падает вниз
      piece.style.setProperty('--rot', (Math.random() * 720 - 360) + 'deg');
      document.body.appendChild(piece);
      setTimeout(removeLater(piece), 1100);
    }
  }
  function removeLater(el) { return function () { el.remove(); }; }

  /* ---------- отметка привычки без перезагрузки ---------- */
  function swap(doc, selector) {
    var current = document.querySelector(selector);
    var fresh = doc.querySelector(selector);
    if (current && fresh) { current.replaceWith(document.importNode(fresh, true)); }
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.classList || !form.classList.contains('toggle-form')) { return; }
    e.preventDefault();

    var item = form.closest('.habit');
    var id = item ? item.getAttribute('data-id') : null;
    var wasDone = !!item && item.classList.contains('done');
    var allDoneBefore = !!document.querySelector('.all-done');
    var button = form.querySelector('button');
    if (button) { button.disabled = true; }

    fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) { throw new Error('HTTP ' + r.status); } return r.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        swap(doc, 'main');
        swap(doc, 'header.top');
        initPage();
        var fresh = id ? document.querySelector('.habit[data-id="' + id + '"]') : null;
        if (!wasDone && fresh && fresh.classList.contains('done')) {
          confetti(fresh.querySelector('.check'), fresh.style.getPropertyValue('--c'));
        }
        if (!allDoneBefore && document.querySelector('.all-done')) {
          confetti(document.querySelector('.all-done'), null, 70);
        }
      })
      .catch(function () { form.submit(); });   // что-то пошло не так: обычная отправка формы
  });

  /* ---------- действия при загрузке страницы ---------- */
  function initPage() {
    markSettings();
    // Часовой пояс браузера (при регистрации)
    var tz = document.querySelector('input[name="tz"][data-auto]');
    if (tz && window.Intl && Intl.DateTimeFormat) {
      try { tz.value = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (err) { /* ничего */ }
    }
    // Тепловая карта: показываем самые свежие недели (справа)
    document.querySelectorAll('.heat-scroll').forEach(function (el) { el.scrollLeft = el.scrollWidth; });
    // Ссылка «Новое растение» из сада открывает форму на главной
    if (location.hash === '#new') {
      var add = document.getElementById('new');
      if (add) { add.open = true; add.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    }
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initPage); }
  else { initPage(); }
})();
