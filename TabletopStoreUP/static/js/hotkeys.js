(function () {
  const isEditable = (el) =>
    el && (
      el.tagName === "INPUT" ||
      el.tagName === "TEXTAREA" ||
      el.isContentEditable ||
      (el.tagName === "SELECT")
    );

  // берём URL-ы и контекст из data-* на <body>
  const $body = document.body;
  const urls = {
    home: $body.dataset.urlHome,
    catalog: $body.dataset.urlCatalog,
    cart: $body.dataset.urlCart,
    checkout: $body.dataset.urlCheckout,
    filters: $body.dataset.urlFilters,        // можно оставить пустым
    next: $body.dataset.urlNext,              // прокидывать из шаблонов со списками
    prev: $body.dataset.urlPrev,
    adminOrders: $body.dataset.urlAdminOrders, // только для менеджеров/админов
    toggleTheme: $body.dataset.urlToggleTheme // POST/GET — неважно, просто вызовем
  };
  const role = $body.dataset.role || "guest";

  // утилиты
  const go = (url) => { if (url) location.assign(url); };
  const focusSearch = () => {
    const search = document.querySelector('#searchInput, [name="q"], [type="search"]');
    if (search) { search.focus(); search.select?.(); }
  };
  const openFilters = () => {
    // поддержка offcanvas/accordion/sidepanel — пробуем по популярным id/class
    const offcanvas = document.querySelector('.offcanvas#filters, [data-filters-panel="1"]');
    if (offcanvas) {
      // bootstrap offcanvas
      if (window.bootstrap?.Offcanvas) {
        const instance = bootstrap.Offcanvas.getOrCreateInstance(offcanvas);
        instance.show();
      } else {
        offcanvas.classList.add('show');
        offcanvas.style.display = 'block';
      }
      return;
    }
    // fallback: клик по кнопке "Фильтры"
    const btn = document.querySelector('[data-action="open-filters"], button#openFilters');
    btn?.click();
  };
  const toggleTheme = async () => {
    // 1) мгновенно переключаем класс на клиенте
    document.documentElement.classList.toggle('theme-dark');
    // 2) уведомляем сервер (если эндпойнт есть)
    if (urls.toggleTheme) {
      try { await fetch(urls.toggleTheme, { method: 'POST', headers: {'X-Requested-With':'XMLHttpRequest','X-CSRFToken':getCSRF()} }); } catch {}
    }
    announce('Тема переключена');
  };
  const announceRegion = (() => {
    let node = document.getElementById('hotkeys-live');
    if (!node) {
      node = document.createElement('div');
      node.id = 'hotkeys-live';
      node.setAttribute('aria-live', 'polite');
      node.className = 'visually-hidden';
      document.body.appendChild(node);
    }
    return node;
  })();
  const announce = (msg) => { announceRegion.textContent = msg; };

  const getCSRF = () => {
    const name = 'csrftoken';
    const m = document.cookie.match(new RegExp('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'));
    return m ? decodeURIComponent(m.pop()) : '';
  };

  const openHelp = () => {
    const modal = document.getElementById('hotkeysModal');
    if (!modal) return;
    if (window.bootstrap?.Modal) {
      bootstrap.Modal.getOrCreateInstance(modal).show();
    } else {
      modal.classList.add('show');
      modal.style.display = 'block';
    }
  };

  // Основные хоткеи:
  // g — каталог
  // / — фокус на поиск
  // c — корзина
  // o — оформить заказ
  // f — фильтры
  // n/p — следующая/предыдущая страница
  // t — тема (светлая/тёмная)
  // ? — помощь (шпаргалка)
  // h — домой
  // r — обновить (без кеша при Shift+R)
  // a — заказы (только менеджер/админ)

  window.addEventListener('keydown', (e) => {
    // не перехватываем, если пользователь печатает, кроме некоторых клавиш
    const typing = isEditable(e.target);

    const key = e.key;           // уже локализован браузером
    const code = e.code;         // физический код
    const shift = e.shiftKey;

    // '?' обычно это Shift + '/'
    if (key === '?' || (shift && key === '/')) {
      e.preventDefault();
      openHelp();
      return;
    }

    if (typing) {
      // разрешаем только несколько глобальных:
      if (key === 'Escape') {
        // закрыть фильтры/модалки, если открыты
        const opened = document.querySelector('.offcanvas.show, .modal.show');
        if (opened) opened.querySelector('[data-bs-dismiss="offcanvas"], [data-bs-dismiss="modal"], .btn-close')?.click();
      }
      return; // прочие — не трогаем
    }

    switch (key) {
      case 'g':      e.preventDefault(); go(urls.catalog); break;
      case '/':      e.preventDefault(); focusSearch(); break;
      case 'c':      e.preventDefault(); go(urls.cart); break;
      case 'o':      e.preventDefault(); go(urls.checkout); break;
      case 'f':
        e.preventDefault();
        // 1) Пытаемся найти offcanvas на странице
        const panel = document.querySelector('#filters.offcanvas, .offcanvas#filters, [data-filters-panel="1"]');
        if (panel) {
            // 2) Открываем через Bootstrap API, если он есть
            if (window.bootstrap?.Offcanvas) {
            bootstrap.Offcanvas.getOrCreateInstance(panel).show();
            } else {
            // 3) Fallback без Bootstrap (минимум, чтобы увидеть панель)
            panel.classList.add('show');
            panel.style.display = 'block';
            panel.removeAttribute('aria-hidden');
            document.body.classList.add('offcanvas-backdrop', 'show');
            }
        } else {
            // 4) Если панели нет на этой странице — переходим по ссылке фильтров (если задана)
            go(urls.filters);
        }
        break;
      case 'n':      e.preventDefault(); go(urls.next); break;
      case 'p':      e.preventDefault(); go(urls.prev); break;
      case 't':      e.preventDefault(); toggleTheme(); break;
      case 'h':      e.preventDefault(); go(urls.home); break;
      case 'r':      e.preventDefault(); shift ? location.reload(true) : location.reload(); break;
      case 'a':
        if (role === 'manager' || role === 'admin' || role === 'staff' || role === 'superuser') {
          e.preventDefault(); go(urls.adminOrders);
        }
        break;
      default:
        break;
    }
  });
})();
