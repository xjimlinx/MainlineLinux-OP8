/* SPDX-License-Identifier: GPL-2.0-only */
/* ABL handoff checkpoint: request a standard PSCI reset immediately. */
.section .text
.global _start
_start:
	b .Lreset
	.word 0
	.quad 0x80000
	.quad .Lend - _start
	.quad 0x0a
	.quad 0
	.quad 0
	.quad 0
	.ascii "ARMd"
	.word 0

.Lreset:
	movz x0, #0x0009
	movk x0, #0x8400, lsl #16
	smc #0
	movz x0, #0x0009
	movk x0, #0x8400, lsl #16
	hvc #0
.Lhang:
	wfe
	b .Lhang

.balign 0x1000
.Lend:
