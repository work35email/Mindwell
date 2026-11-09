(function () {
  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  var chat = document.querySelector("#chat-form");
  if (chat && window.fetch) {
    document.querySelectorAll("[data-mode]").forEach(function (button) {
      button.addEventListener("click", function () {
        var mode = button.getAttribute("data-mode") || "listen";
        var field = document.querySelector("#companion-mode");
        if (field) field.value = mode;
        document.querySelectorAll("[data-mode]").forEach(function (other) {
          other.classList.toggle("on", other === button);
        });
      });
    });
    document.querySelectorAll(".chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var field = chat.querySelector("textarea");
        field.value = chip.getAttribute("data-text") || chip.textContent;
        if (chat.requestSubmit) chat.requestSubmit();
        else chat.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    });
    chat.addEventListener("submit", function (event) {
      event.preventDefault();
      var field = chat.querySelector("textarea");
      var text = (field.value || "").trim();
      if (!text) return;
      var thread = document.querySelector("#thread");
      var welcome = document.querySelector("#welcome");
      if (welcome) welcome.hidden = true;
      if (thread) thread.hidden = false;
      var clearer = document.querySelector("#clear-chat-button");
      if (clearer) clearer.hidden = false;
      append(thread, "user", text, "normal");
      field.value = "";
      var pending = append(thread, "assistant", "···", "normal");
      pending.classList.add("typing");
      var modeField = document.querySelector("#companion-mode");
      fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrf()
        },
        body: JSON.stringify({ message: text, mode: modeField ? modeField.value : "listen" })
      }).then(function (response) {
        return response.json().then(function (payload) { return { ok: response.ok, payload: payload }; });
      }).then(function (result) {
        pending.remove();
        if (!result.ok) {
          append(thread, "assistant", chat.getAttribute("data-error") || "Error", "fallback");
          return;
        }
        var bubble = append(thread, "assistant", result.payload.reply || "", result.payload.level || "normal");
        if (result.payload.level === "crisis" || result.payload.level === "abuse" || result.payload.level === "medical") {
          var link = document.createElement("a");
          link.href = "/support";
          link.textContent = chat.getAttribute("data-support") || "Support";
          bubble.appendChild(link);
        }
        renderCards(bubble, result.payload.cards || [], result.payload.level);
        renderSuggestions(result.payload.suggestions || []);
      }).catch(function () {
        pending.remove();
        append(thread, "assistant", chat.getAttribute("data-error") || "Error", "fallback");
      });
    });
  }

  function append(thread, role, content, level) {
    var item = document.createElement("li");
    item.className = "bubble " + role + " level-" + (level || "normal");
    var paragraph = document.createElement("p");
    paragraph.textContent = content;
    item.appendChild(paragraph);
    var meta = document.createElement("span");
    meta.className = "meta";
    var now = new Date();
    meta.textContent = now.getHours() + ":" + String(now.getMinutes()).padStart(2, "0");
    item.appendChild(meta);
    thread.appendChild(item);
    item.scrollIntoView({ block: "nearest" });
    return item;
  }

  function renderCards(bubble, cards, level) {
    if (!cards.length || level !== "normal" || !chat) return;
    var box = document.createElement("div");
    box.className = "resource-cards";
    var heading = document.createElement("p");
    heading.className = "hint";
    heading.textContent = (chat.getAttribute("data-recommend") || "") + " · " + (chat.getAttribute("data-based") || "");
    box.appendChild(heading);
    var pattern = chat.getAttribute("data-minutes") || "{count} min";
    cards.forEach(function (card) {
      var link = document.createElement("a");
      link.className = "resource-card";
      link.href = "/library/" + card.id;
      var title = document.createElement("strong");
      title.textContent = card.title || "";
      var detail = document.createElement("span");
      var minutes = card.minutes ? " · " + pattern.replace("{count}", card.minutes) : "";
      detail.textContent = (card.preview || "") + minutes;
      var open = document.createElement("em");
      open.textContent = chat.getAttribute("data-open") || "";
      link.appendChild(title);
      link.appendChild(detail);
      link.appendChild(open);
      box.appendChild(link);
    });
    bubble.appendChild(box);
  }

  function renderSuggestions(items) {
    var box = document.querySelector("#suggestions");
    if (!box) return;
    box.textContent = "";
    items.forEach(function (item) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = item.label || item.text || "";
      chip.addEventListener("click", function () {
        var field = chat.querySelector("textarea");
        field.value = item.text || chip.textContent;
        if (chat.requestSubmit) chat.requestSubmit();
        else chat.dispatchEvent(new Event("submit", { cancelable: true }));
      });
      box.appendChild(chip);
    });
  }

  document.querySelectorAll(".prompt").forEach(function (button) {
    button.addEventListener("click", function () {
      var area = document.querySelector("#journal-body");
      if (!area) return;
      var line = button.getAttribute("data-prompt") || "";
      if (!line) return;
      if (!area.value.trim()) area.value = line + " ";
      else if (area.value.indexOf(line) === -1) area.value = line + "\n" + area.value;
      area.focus();
    });
  });

  var record = document.querySelector("#record");
  var stop = document.querySelector("#stop");
  var status = document.querySelector("#rec-status");
  if (record) {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      record.hidden = true;
    } else {
      var recorder = null;
      var chunks = [];
      var stream = null;
      record.addEventListener("click", function () {
        navigator.mediaDevices.getUserMedia({ audio: true }).then(function (mic) {
          stream = mic;
          chunks = [];
          recorder = new MediaRecorder(mic);
          recorder.ondataavailable = function (event) {
            if (event.data && event.data.size) chunks.push(event.data);
          };
          recorder.onstop = function () {
            if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
            var blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
            var body = new FormData();
            body.append("audio", blob, "journal.webm");
            var language = document.querySelector("#journal-language");
            body.append("language", language ? language.value : "en");
            if (status) status.textContent = record.getAttribute("data-transcribing") || "";
            fetch("/api/transcribe", {
              method: "POST",
              headers: { "X-CSRFToken": csrf() },
              body: body
            }).then(function (response) {
              return response.json().then(function (payload) { return { ok: response.ok, payload: payload }; });
            }).then(function (result) {
              var area = document.querySelector("#journal-body");
              if (result.ok && result.payload.text != null) {
                area.value = result.payload.text;
                var source = document.querySelector("#journal-source");
                if (source) source.value = "voice";
                if (status) status.textContent = record.getAttribute("data-edit") || "";
              } else if (status) {
                status.textContent = (result.payload && result.payload.message) || record.getAttribute("data-needs-groq") || "";
              }
            }).catch(function () {
              if (status) status.textContent = record.getAttribute("data-needs-groq") || "";
            });
          };
          recorder.start();
          record.hidden = true;
          stop.hidden = false;
          if (status) status.textContent = record.getAttribute("data-recording") || "";
        }).catch(function () {
          if (status) status.textContent = record.getAttribute("data-denied") || "";
        });
      });
      stop.addEventListener("click", function () {
        if (recorder && recorder.state !== "inactive") recorder.stop();
        stop.hidden = true;
        record.hidden = false;
      });
    }
  }

  var moodForm = document.querySelector("[data-mood-form]");
  var selectedMood = document.querySelector("#mood-selected-label");
  if (moodForm && selectedMood) {
    moodForm.addEventListener("change", function () {
      var picked = moodForm.querySelector('input[name="mood"]:checked');
      if (!picked) return;
      var label = picked.closest("label");
      if (!label) return;
      var face = label.querySelector(".emoji");
      var word = label.querySelector("small");
      selectedMood.textContent = ((face && face.textContent) || "") + " " + ((word && word.textContent) || "");
    });
  }

  function parseIso(value) {
    var parts = (value || "").split("-");
    if (parts.length !== 3) return null;
    var day = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return isNaN(day.getTime()) ? null : day;
  }
  function toIso(day) {
    var month = day.getMonth() + 1;
    var date = day.getDate();
    return day.getFullYear() + "-" + (month < 10 ? "0" : "") + month + "-" + (date < 10 ? "0" : "") + date;
  }

  document.querySelectorAll("[data-date-field]").forEach(function (field) {
    var input = field.querySelector("input[name='date']");
    var trigger = field.querySelector(".date-trigger");
    var readout = field.querySelector(".date-readout");
    var pop = field.querySelector(".date-pop");
    var title = field.querySelector(".date-title");
    var week = field.querySelector(".date-week");
    var grid = field.querySelector(".date-grid");
    if (!input || !trigger || !pop) return;
    var lang = document.documentElement.lang || "en";
    var maxDay = parseIso(field.getAttribute("data-max")) || new Date();
    var minDay = new Date(maxDay.getFullYear(), maxDay.getMonth(), maxDay.getDate() - 400);
    var selected = parseIso(input.value) || maxDay;
    var view = new Date(selected.getFullYear(), selected.getMonth(), 1);
    var dayFormat = new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric" });
    var monthFormat = new Intl.DateTimeFormat(lang, { month: "long", year: "numeric" });
    var weekFormat = new Intl.DateTimeFormat(lang, { weekday: "short" });

    function allowed(day) {
      var key = toIso(day);
      return key >= toIso(minDay) && key <= toIso(maxDay);
    }
    function showReadout() {
      readout.textContent = dayFormat.format(selected);
    }
    function closePop() {
      pop.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }
    function paint() {
      title.textContent = monthFormat.format(view);
      week.innerHTML = "";
      var monday = new Date(2024, 0, 1);
      for (var index = 0; index < 7; index += 1) {
        var name = document.createElement("span");
        var sample = new Date(monday);
        sample.setDate(monday.getDate() + index);
        name.textContent = weekFormat.format(sample);
        week.appendChild(name);
      }
      grid.innerHTML = "";
      var first = new Date(view.getFullYear(), view.getMonth(), 1);
      var lead = (first.getDay() + 6) % 7;
      var cursor = new Date(first);
      cursor.setDate(1 - lead);
      for (var cell = 0; cell < 42; cell += 1) {
        var day = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate());
        var button = document.createElement("button");
        button.type = "button";
        button.className = "date-day";
        button.textContent = String(day.getDate());
        if (day.getMonth() !== view.getMonth()) button.classList.add("is-out");
        if (toIso(day) === toIso(selected)) button.classList.add("is-on");
        if (!allowed(day)) button.disabled = true;
        button.addEventListener("click", function (event) {
          var picked = event.currentTarget._day;
          if (!allowed(picked)) return;
          selected = picked;
          input.value = toIso(selected);
          showReadout();
          closePop();
        });
        button._day = day;
        grid.appendChild(button);
        cursor.setDate(cursor.getDate() + 1);
      }
    }
    trigger.addEventListener("click", function () {
      if (pop.hidden) {
        view = new Date(selected.getFullYear(), selected.getMonth(), 1);
        paint();
        pop.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
      } else {
        closePop();
      }
    });
    field.querySelector("[data-date-prev]").addEventListener("click", function () {
      view = new Date(view.getFullYear(), view.getMonth() - 1, 1);
      paint();
    });
    field.querySelector("[data-date-next]").addEventListener("click", function () {
      view = new Date(view.getFullYear(), view.getMonth() + 1, 1);
      paint();
    });
    document.addEventListener("click", function (event) {
      if (!field.contains(event.target)) closePop();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closePop();
    });
    showReadout();
  });
})();
