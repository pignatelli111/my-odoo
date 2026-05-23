/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { SbuHelpDialog } from "./sbu_help_dialog";

export class SbuHelpMain extends Component {
    static template = "sbu_ui_help.SbuHelpMain";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            model: null,
            viewMode: null,
        });
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this._syncContext();
        });
        this._syncContext();
    }

    _syncContext() {
        const ctrl = this.actionService.currentController;
        if (!ctrl?.props?.resModel) {
            this.state.model = null;
            this.state.viewMode = null;
            return;
        }
        this.state.model = ctrl.props.resModel;
        const viewType = ctrl.props.type || ctrl.view?.type;
        this.state.viewMode = viewType || "form";
    }

    get showFab() {
        return Boolean(this.state.model);
    }

    get fabTitle() {
        return _t("Help for this screen");
    }

    async openHelp() {
        if (!this.state.model) {
            return;
        }
        const helpPromise = this.orm.call(
            "sbu.ui.help.topic",
            "get_help_for_ui",
            [],
            {
                model: this.state.model,
                view_mode: this.state.viewMode,
            }
        );
        this.dialog.add(SbuHelpDialog, {
            help: await helpPromise,
            loading: false,
        }, {
            title: _t("Screen help"),
            size: "lg",
        });
    }
}

registry.category("main_components").add("SbuHelpMain", {
    Component: SbuHelpMain,
});
