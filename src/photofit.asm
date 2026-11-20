; photofit.asm — main-image glue for the photofit faces held in banks 3, 4
; and 6 (photofit3/4/6.asm). These routines page those banks in at #C000,
; so they must themselves sit below #C000 (asserted at the end).

; A = subject name index (0..SUBJ_NAME_COUNT-1), or #FF for the mirror
; level's fixed face. Fixes the subject's features for both portraits.
pf_select:
    ld e, a
    ld a, PF_BANK_A
    call page_in
    ld a, e
    call pf4.select
    jp page_home

; Draws the dossier face on the level intro screen.
pf_dossier:
    ld a, PF_BANK_A
    call page_in
    call pf4.begin
    ld a, PF_BANK_B
    call page_in
    call pf3.hair
    ld a, PF_BANK_A
    call page_in
    call pf4.finish
    jp page_home

; Draws the interrogation portrait for the selected subject. Glitch effects
; call this to repair the portrait, which is then just a copy from bank 6.
draw_portrait:
    ld a, PF_BANK_SMALL
    call page_in
    call pf6.draw
    jp page_home

    ASSERT $ <= #C000, "photofit paging glue must stay below #C000"
