/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { router, routerBus } from "@web/core/browser/router";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted } from "@odoo/owl";
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
            viewMode: "form",
        });
        const sync = () => this._syncContext();
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", sync);
        useBus(routerBus, "ROUTE_CHANGE", sync);
        onMounted(sync);
        sync();
    }

    _syncContext() {
        const ctrl = this.actionService.currentController;
        const props = ctrl?.props || {};
        const action = ctrl?.action || {};
        const route = router.current || {};
        const stackTop = route.actionStack?.length
            ? route.actionStack[route.actionStack.length - 1]
            : null;
        const model =
            props.resModel ||
            action.res_model ||
            route.model ||
            stackTop?.model ||
            null;
        this.state.model = model;
        this.state.viewMode = props.type || ctrl?.view?.type || stackTop?.view_type || "form";
    }

    get fabTitle() {
        return _t("Help for this screen");
    }

    async openHelp() {
        let help;
        if (this.state.model) {
            help = await this.orm.call(
                "sbu.ui.help.topic",
                "get_help_for_ui",
                [],
                {
                    model: this.state.model,
                    view_mode: this.state.viewMode,
                }
            );
        } else {
            help = {
                title: _t("Screen help"),
                purpose: _t(
                    "<p>Open a list or form (e.g. <strong>Estimates</strong>, "
                    + "<strong>Purchase requests</strong>, <strong>Project</strong>) "
                    + "then click <strong>?</strong> again for a detailed guide.</p>"
                ),
                sections: [],
            };
        }
        this.dialog.add(
            SbuHelpDialog,
            { help },
            {
                title: help?.title || _t("Screen help"),
                size: "lg",
            }
        );
    }
}

registry.category("main_components").add("SbuHelpMain", {
    Component: SbuHelpMain,
    sequence: 50,
});
