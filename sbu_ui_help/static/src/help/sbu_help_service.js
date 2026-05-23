/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { router } from "@web/core/browser/router";
import { SbuHelpDialog } from "./sbu_help_dialog";

const SECTION_LABELS = {
    overview: () => _t("Overview"),
    button: () => _t("Buttons & actions"),
    tab: () => _t("Tabs"),
    stat: () => _t("Smart buttons (top)"),
    filter: () => _t("Filters & search"),
    field: () => _t("Important fields"),
    menu: () => _t("Menus"),
};

function escapeHtml(text) {
    return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function helpPayloadToHtml(help) {
    if (!help) {
        return `<p>${escapeHtml(_t("No help content."))}</p>`;
    }
    const parts = [];
    if (help.purpose) {
        parts.push(`<div class="o_sbu_help_purpose mb-3">${help.purpose}</div>`);
    }
    const sections = help.sections || [];
    if (sections.length) {
        const groups = {};
        for (const sec of sections) {
            const key = sec.type || "button";
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(sec);
        }
        for (const [type, items] of Object.entries(groups)) {
            const label = (SECTION_LABELS[type] || (() => type))();
            parts.push(`<h5 class="mt-3 mb-2 text-primary">${escapeHtml(label)}</h5>`);
            parts.push('<div class="list-group list-group-flush mb-2">');
            for (const item of items) {
                parts.push('<div class="list-group-item px-0 border-0 border-bottom">');
                parts.push(`<strong>${escapeHtml(item.title || "")}</strong>`);
                if (item.body) {
                    parts.push(`<div class="text-muted small mt-1">${item.body}</div>`);
                }
                parts.push("</div>");
            }
            parts.push("</div>");
        }
    } else if (!help.purpose) {
        parts.push(
            `<p class="text-muted mb-0">${escapeHtml(
                _t(
                    "Use the fields and buttons on this form as usual. Contact your SBU administrator to extend this guide."
                )
            )}</p>`
        );
    }
    return parts.join("");
}

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
            let viewMode = props.type || ctrl?.view?.type || stackTop?.view_type || "form";
            if (viewMode === "tree") {
                viewMode = "list";
            }
            return {
                model:
                    props.resModel ||
                    act.res_model ||
                    route.model ||
                    stackTop?.model ||
                    null,
                viewMode,
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
                        "<p>Help is not available. Upgrade module <strong>sbu_ui_help</strong> "
                        + "and refresh the page (Ctrl+F5).</p>"
                    ),
                    sections: [],
                };
            }
            const title = help?.title || _t("Screen help");
            const bodyHtml = helpPayloadToHtml(help);
            try {
                dialog.add(SbuHelpDialog, { title, bodyHtml });
            } catch (error) {
                console.error("SBU help: dialog failed", error);
                notification.add(_t("Could not open help window."), { type: "danger" });
            }
        };

        return { openHelp, getScreenContext };
    },
};

registry.category("services").add("sbu_help", sbuHelpService);
