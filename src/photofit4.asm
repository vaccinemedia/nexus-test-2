; photofit4.asm — bank 4 at #C000: picks each subject's photofit features
; and draws the dossier face from the head up to the mouth (and glasses,
; which go on after bank 3 has drawn the hair). Entered via photofit.asm.

    MODULE pf4
    ORG #C000

select: jp select_impl              ; A = subject name index, #FF = Deckard
begin:  jp begin_impl               ; clear the panel, draw head .. mouth
finish: jp finish_impl              ; glasses

; ---------------------------------------------------------------------------
; Feature selection. tools/photofit/pfselect.py mirrors this step for step,
; so the previews it renders match the game exactly.
select_impl:
    ld c, a
    xor a
    ld (pf_built), a
    ld a, c
    inc a
    jr nz, .random
    ld hl, pf_deckard
    ld de, pf_sel
    ld bc, PF_SEL_LEN + 2           ; features, skin, hair colour
    ldir
    ret
.random:
    ld hl, (current_subject + SUBJ_PORTRAIT)
    ld a, h
    or l
    jr nz, .seeded
    inc l                           ; xorshift must not start at zero
.seeded:
    ld (pf_rng), hl
    ld b, 0
    ld hl, pf_gender
    add hl, bc
    ld a, (hl)
    cp 2
    jr c, .gendered
    call rand                       ; name could be either
    and 1
.gendered:
    add a, a
    add a, a
    add a, a
    ld (gender_ofs), a              ; 0 = male list, 8 = female list
    ld hl, pf_lists
    ld de, pf_sel
    ld b, PF_SEL_LEN
.cat:
    push bc
    push hl
    call rand
    and 7
    ld c, a
    ld a, (gender_ofs)
    add a, c
    ld c, a
    ld b, 0
    pop hl
    push hl
    add hl, bc
    ld a, (hl)
    ld (de), a
    inc de
    pop hl
    ld bc, 16
    add hl, bc
    pop bc
    djnz .cat
    call rand
    and 3
    ld (de), a                      ; pf_skin
    inc de
    call rand
    and 3
    ld (de), a                      ; pf_hairc
    ret

; 16-bit xorshift. Returns A; clobbers HL.
rand:
    ld hl, (pf_rng)
    ld a, h
    rra
    ld a, l
    rra
    xor h
    ld h, a
    ld a, l
    rra
    ld a, h
    rra
    xor l
    ld l, a
    xor h
    ld h, a
    ld (pf_rng), hl
    ret

gender_ofs: DB 0

; ---------------------------------------------------------------------------
begin_impl:
    ; Panel: black lines on the subject's skin colour
    ld a, (pf_skin)
    ld e, a
    ld d, 0
    ld hl, skin_paper
    add hl, de
    ld a, (hl)
    ld hl, ATTR_BASE + PF_PANEL_ROW * 32 + PF_PANEL_COL
    ld c, PF_LH / 8
.arow:
    ld b, PF_LW
.acol:
    ld (hl), a
    inc hl
    djnz .acol
    ld de, 32 - PF_LW
    add hl, de
    dec c
    jr nz, .arow

    call start
    ld hl, PF_LW * PF_LH
.clear:
    xor a
    ld (de), a
    call advance
    dec hl
    ld a, h
    or l
    jr nz, .clear

    ld a, (pf_sel + PF_HEAD)
    ld hl, pfl_head_tab
    call feature
    ld a, (pf_sel + PF_COLLAR)
    ld hl, pfl_collar_tab
    call feature
    ld a, (pf_sel + PF_MARKS)
    call is_glasses
    jr c, .no_marks
    ld a, (pf_sel + PF_MARKS)
    ld hl, pfl_marks_tab
    call feature
.no_marks:
    ld a, (pf_sel + PF_EYES)
    ld hl, pfl_eyes_tab
    call feature
    ld a, (pf_sel + PF_BROWS)
    ld hl, pfl_brows_tab
    call feature
    ld a, (pf_sel + PF_NOSE)
    ld hl, pfl_nose_tab
    call feature
    ld a, (pf_sel + PF_MOUTH)
    ld hl, pfl_mouth_tab
    jp feature

finish_impl:
    ld a, (pf_sel + PF_MARKS)
    call is_glasses
    ret nc
    ld a, (pf_sel + PF_MARKS)
    ld hl, pfl_marks_tab
    jp feature

; Carry set if A is a glasses mark (variants 1 and 2), which are drawn over
; the hair rather than under it.
is_glasses:
    dec a
    cp 2
    ret

skin_paper:
    DB INK_WHITE*8 + BRIGHT, INK_YELLOW*8 + BRIGHT, INK_CYAN*8 + BRIGHT, INK_WHITE*8

    INCLUDE "pf_dossier_draw.inc"
    INCLUDE "photofit_large_a.inc"

    INCLUDE "photofit_select.inc"
End:
    ASSERT End <= IM2_STUB, "photofit bank 4 is full"
    ENDMODULE
