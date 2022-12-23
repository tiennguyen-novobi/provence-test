/** @odoo-module */

odoo.define('l10n_pdf_preview.pdf_preview', function(require) {
    "use strict";
    let core = require('web.core');
    let session = require('web.session');
    import { registry } from "@web/core/registry";
    let _t = core._t;

    function _getReportUrl(action, type) {
        let url = `/report/${type}/${action.report_name}`;
        const actionContext = action.context || {};
        if (action.data && JSON.stringify(action.data) !== "{}") {
            // build a query string with `action.data` (it's the place where reports
            // using a wizard to customize the output traditionally put their options)
            const options = encodeURIComponent(JSON.stringify(action.data));
            const context = encodeURIComponent(JSON.stringify(actionContext));
            url += `?options=${options}&context=${context}`;
        } else {
            if (actionContext.active_ids) {
                url += `/${actionContext.active_ids.join(",")}`;
            }
            if (type === "html") {
                const context = encodeURIComponent(JSON.stringify(env.services.user.context));
                url += `?context=${context}`;
            }
        }
        return url;
    }

    async function _triggerPreview(action, options, type, env) {
        const url = _getReportUrl(action, type);
        env.services.ui.block();
        try {
            let type = 'qweb-' + url.split('/')[2];
            let params = {
                data: JSON.stringify([url, action.report_type]),
                context: JSON.stringify(env.services.user.context),
            }
            let url2 = session.url('/report/download', params);
            if (!window.open(url2)) {
                let message = _t('A popup window with your report was blocked. You ' +
                    'may need to change your browser settings to allow ' +
                    'popup windows for this page.');
                env.services.notification.add(message, {
                    title: _t("Warning"),
                });
                return false
            }
        } finally {
            env.services.ui.unblock();
        }

        const onClose = options.onClose;
        if (action.close_on_report_download) {
            env.services.action.doAction({ type: "ir.actions.act_window_close" }, { onClose });
        } else if (onClose) {
            onClose();
        }
        return true
    }

    async function PreviewPdfReportActionHandler(action, options, env){
        if (action.report_type === 'qweb-pdf') {
            return _triggerPreview(action, options, "pdf", env);
        }
        return false;
    }

    registry
        .category("ir.actions.report handlers")
        .add("pdf_preview_handler", PreviewPdfReportActionHandler);
})
