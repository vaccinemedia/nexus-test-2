; photofit.asm — main-image glue for the photofit faces held in banks 3, 4
; and 6 (photofit3/4/6.asm). These routines page those banks in at #C000,
; so they must themselves sit below #C000 (asserted at the end).

; A = subject name index (0..SUBJ_NAME_COUNT-1), or #FF for the mirror
; level's fixed face. Fixes the subject's features for both portraits.
pf_select:
    ld e, a
    ld a, PF_BANK_A
    call pf_page
    ld a, e
    call pf4.select
    jr pf_page_home

; Draws the dossier face on the level intro screen.
pf_dossier:
    ld a, PF_BANK_A
    call pf_page
    call pf4.begin
    ld a, PF_BANK_B
    call pf_page
    call pf3.hair
    ld a, PF_BANK_A
    call pf_page
    call pf4.finish
    jr pf_page_home

; Draws the interrogation portrait for the selected subject. Glitch effects
; call this to repair the portrait, which is then just a copy from bank 6.
draw_portrait:
    ld a, PF_BANK_SMALL
    call pf_page
    call pf6.draw
pf_page_home:
    ld a, BANK_0_48ROM
pf_page:
    ld bc, PORT_128MEM
    out (c), a
    ret

; Loads the photofit banks from the headerless tape blocks that follow the
; BASIC-loaded program. Runs once at start-up, after verify_paging has
; finished scribbling on banks 4 and 6.
pf_load_banks:
    ld a, (paging_ok)
    or a
    ret z
    ld hl, pf_tape_blocks
.block:
    ld a, (hl)
    or a
    jr z, pf_page_home
    inc hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push hl
    call pf_page
    ld ix, #C000
    ld iy, ROM_SYSVARS              ; LD-BYTES re-enables interrupts on exit
    ld a, #FF
    scf
    call ROM_LD_BYTES
    di
    call music_isr_stub
    pop hl
    jr .block

pf_tape_blocks:
    DB PF_BANK_SMALL
    DW pf6.End - #C000
    DB PF_BANK_A
    DW pf4.End - #C000
    DB PF_BANK_B
    DW pf3.End - #C000
    DB 0

    ASSERT $ <= #C000, "photofit paging glue must stay below #C000"
