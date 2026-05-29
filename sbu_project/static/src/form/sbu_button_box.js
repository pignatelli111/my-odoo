/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onWillRender } from "@odoo/owl";
import { ButtonBox } from "@web/views/form/button_box/button_box";

/**
 * Odoo groups overflow stat buttons into a "More" dropdown (limit depends on ui.size).
 * SBU project forms need every smart button visible (Tasks, Logikal, RDA, SAL, …).
 */
const SBU_MAX_VISIBLE_STAT_BUTTONS = 64;

patch(ButtonBox.prototype, {
    setup() {
        onWillRender(() => {
            const allVisibleButtons = Object.entries(this.props.slots)
                .filter(([_, slot]) => this.isSlotVisible(slot))
                .map(([slotName]) => slotName);
            const maxVisibleButtons = SBU_MAX_VISIBLE_STAT_BUTTONS;
            if (allVisibleButtons.length <= maxVisibleButtons) {
                this.visibleButtons = allVisibleButtons;
                this.additionalButtons = [];
                this.isFull = allVisibleButtons.length >= 8;
            } else {
                const splitIndex = Math.max(maxVisibleButtons - 1, 0);
                this.visibleButtons = allVisibleButtons.slice(0, splitIndex);
                this.additionalButtons = allVisibleButtons.slice(splitIndex);
                this.isFull = true;
            }
        });
    },
});
