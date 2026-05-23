/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, markup } from "@odoo/owl";

export class SbuHelpDialog extends Component {
    static template = "sbu_ui_help.SbuHelpDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
        bodyHtml: { type: String, optional: true },
    };

    setup() {
        if (this.env.dialogData) {
            this.env.dialogData.dismiss = () => this.props.close();
        }
    }

    get dialogTitle() {
        return this.props.title || _t("Screen help");
    }

    get bodyMarkup() {
        const html = this.props.bodyHtml || "";
        return markup(html);
    }

    get closeLabel() {
        return _t("Close");
    }

    onClose() {
        this.props.close();
    }
}
