/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";

const SECTION_LABELS = {
    overview: () => _t("Overview"),
    button: () => _t("Buttons & actions"),
    tab: () => _t("Tabs"),
    stat: () => _t("Smart buttons (top)"),
    filter: () => _t("Filters & search"),
    field: () => _t("Important fields"),
    menu: () => _t("Menus"),
};

export class SbuHelpDialog extends Component {
    static template = "sbu_ui_help.SbuHelpDialog";
    static props = {
        close: Function,
        help: { type: [Object, Boolean], optional: true },
        loading: { type: Boolean, optional: true },
    };

    get title() {
        return this.props.help?.title || _t("Screen help");
    }

    get groupedSections() {
        const sections = this.props.help?.sections || [];
        const groups = {};
        for (const sec of sections) {
            const key = sec.type || "button";
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(sec);
        }
        return Object.entries(groups).map(([type, items]) => ({
            type,
            label: (SECTION_LABELS[type] || (() => type))(),
            items,
        }));
    }

    get hasSections() {
        return (this.props.help?.sections || []).length > 0;
    }

    get closeLabel() {
        return _t("Close");
    }

    get emptyHint() {
        return _t(
            "Use the fields and buttons on this form as usual. Contact your SBU administrator to extend this guide."
        );
    }
}
