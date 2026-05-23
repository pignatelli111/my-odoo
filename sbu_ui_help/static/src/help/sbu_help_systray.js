/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class SbuHelpSystray extends Component {
    static template = "sbu_ui_help.SbuHelpSystray";
    static props = {};

    setup() {
        this.sbuHelp = useService("sbu_help");
    }

    get title() {
        return _t("Help for this screen");
    }

    onClick() {
        this.sbuHelp.openHelp();
    }
}

registry.category("systray").add(
    "sbu_help",
    { Component: SbuHelpSystray },
    { sequence: 25 },
);
