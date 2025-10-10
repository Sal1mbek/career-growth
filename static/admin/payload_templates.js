(function () {
  function setPayloadFromTemplate(selectId, payloadSelector, dataAttr) {
    const select = document.getElementById(selectId);
    const payloadInput = document.querySelector(payloadSelector); // скрытый input JSONEditor
    if (!select || !payloadInput) return;

    const raw = payloadInput.getAttribute(dataAttr);
    if (!raw) return;

    let templates = {};
    try { templates = JSON.parse(raw); } catch (e) { return; }

    function applyTemplate() {
      const key = select.value;
      const tpl = templates[key] || {};
      payloadInput.value = JSON.stringify(tpl, null, 2);
      payloadInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // если создаём новый объект — автозаполним
    const current = (payloadInput.value || "").trim();
    if (!current || current === "{}") {
      applyTemplate();
    }

    select.addEventListener('change', applyTemplate);
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Notifications: подстановка по notification_type
    setPayloadFromTemplate(
      'id_notification_type',
      'textarea[name="payload"], input[name="payload"]',
      'data-notification-templates'
    );

    // Recommendation: подстановка по kind
    setPayloadFromTemplate(
      'id_kind',
      'textarea[name="payload"], input[name="payload"]',
      'data-recommendation-templates'
    );
  });
})();
