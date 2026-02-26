(function () {
  function dateKeyFromCard(card) {
    var link = card.querySelector("a");
    if (!link) {
      return Number.NEGATIVE_INFINITY;
    }

    var href = link.getAttribute("href") || "";
    var folderMatch = /\/(\d{4})-(\d{2})-(\d{2})-/.exec(href);
    if (folderMatch) {
      return Number(folderMatch[1] + folderMatch[2] + folderMatch[3]);
    }

    var dateEl = card.querySelector(".date");
    if (dateEl) {
      var parsed = Date.parse(dateEl.textContent.trim());
      if (!Number.isNaN(parsed)) {
        return parsed;
      }
    }

    return Number.NEGATIVE_INFINITY;
  }

  function limitPostsPerTab(maxPosts) {
    var sections = document.querySelectorAll("[data-tab]");

    sections.forEach(function (section) {
      var cards = Array.prototype.slice.call(section.querySelectorAll(".card"));
      cards.sort(function (a, b) {
        return dateKeyFromCard(b) - dateKeyFromCard(a);
      });

      cards.forEach(function (card, index) {
        if (index < maxPosts) {
          section.appendChild(card);
        } else {
          card.remove();
        }
      });
    });
  }

  function renderMath() {
    if (window.renderMathInElement) {
      window.renderMathInElement(document.body, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false }
        ],
        throwOnError: false
      });
    }
  }

  function selectTab(name) {
    var tabs = document.querySelectorAll("[data-tab]");
    var links = document.querySelectorAll("[data-tab-link]");

    tabs.forEach(function (section) {
      section.hidden = section.getAttribute("data-tab") !== name;
    });

    links.forEach(function (link) {
      var active = link.getAttribute("data-tab-link") === name;
      link.classList.toggle("active", active);
      if (active) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  }

  function initTabs() {
    var links = document.querySelectorAll("[data-tab-link]");
    if (!links.length) {
      return;
    }

    function tabFromHash() {
      if (window.location.hash === "#essays") {
        return "essays";
      }
      return "research";
    }

    links.forEach(function (link) {
      link.addEventListener("click", function () {
        var tab = link.getAttribute("data-tab-link");
        selectTab(tab);
      });
    });

    window.addEventListener("hashchange", function () {
      selectTab(tabFromHash());
    });

    selectTab(tabFromHash());
  }

  document.addEventListener("DOMContentLoaded", function () {
    limitPostsPerTab(2);
    initTabs();
    renderMath();
  });
})();
