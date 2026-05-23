/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { router } from "@web/core/browser/router";
import { SbuHelpDialog } from "./sbu_help_dialog";

export const sbuHelpService = {
    dependencies: ["orm", "action", "dialog", "notification"],
    start(env, { orm, action, dialog, notification }) {
        const getScreenContext = () => {
            const ctrl = action.currentController;
            const props = ctrl?.props || {};
            const act = ctrl?.action || {};
            const route = router.current || {};
            const stackTop = route.actionStack?.length
                ? route.actionStack[route.actionStack.length - 1]
                : null;
            return {
                model:
                    props.resModel ||
                    act.res_model ||
                    route.model ||
                    stackTop?.model ||
                    null,
                viewMode: props.type || ctrl?.view?.type || stackTop?.view_type || "form",
            };
        };

        const openHelp = async () => {
            const { model, viewMode } = getScreenContext();
            let help;
            try {
                if (model) {
                    help = await orm.call(
                        "sbu.ui.help.topic",
                        "get_help_for_ui",
                        [model, viewMode],
                    );
                } else {
                    help = {
                        title: _t("Screen help"),
                        purpose: _t(
                            "<p>Open a list or form (e.g. <strong>Estimates</strong>, "
                            + "<strong>SAL sheets</strong>, <strong>Project</strong>) "
                            + "then open help again for a detailed guide.</p>"
                        ),
                        sections: [],
                    };
                }
            } catch (error) {
                console.error("SBU help: RPC failed", error);
                notification.add(_t("Could not load screen help."), { type: "danger" });
                help = {
                    title: _t("Screen help"),
                    purpose: _t(
                        "<p>Install app <strong>SBU Context Help</strong> (Apps) and upgrade module "
                        + "<code>sbu_ui_help</code>, then refresh the page (Ctrl+F5).</p>"
                    ),
                    sections: [],
                };
            }
            const title = help?.title || _t("Screen help");
            dialog.add(SbuHelpDialog, { help, title });
        };

        return { openHelp, getScreenContext };
    },
};

registry.category("services").add("sbu_help", sbuHelpService);
