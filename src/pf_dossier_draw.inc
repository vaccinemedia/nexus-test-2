; pf_dossier_draw.inc — shared by the two dossier banks (photofit4.asm and
; photofit3.asm, each inside its own MODULE). Draws photofit feature streams
; straight onto the dossier panel: PF_LW bytes x PF_LH pixel lines.
; Stream format: see tools/photofit/build_data.py.

; A = variant, HL = category table. Clears the feature's mask out of the
; picture, then draws its lines.
feature:
    add a, a
    add a, a
    ld e, a
    ld d, 0
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    ld a, (hl)
    inc hl
    ld h, (hl)
    ld l, a
    push hl
    ex de, hl
    call dec_andnot
    pop hl

; HL = stream: picture |= stream
dec_or:
    call start
.next:
    ld a, (hl)
    inc hl
    or a
    ret z
    cp #C0
    jr nc, .ones
    cp #80
    jr nc, .skip
    ld b, a
.lit:
    ld a, (de)
    or (hl)
    ld (de), a
    inc hl
    call advance
    djnz .lit
    jr .next
.ones:
    sub #BF
    ld b, a
.one:
    ld a, #FF
    ld (de), a
    call advance
    djnz .one
    jr .next
.skip:
    sub #7F
    ld b, a
.sk:
    call advance
    djnz .sk
    jr .next

; HL = stream: picture &= ~stream
dec_andnot:
    call start
.next:
    ld a, (hl)
    inc hl
    or a
    ret z
    cp #C0
    jr nc, .zeros
    cp #80
    jr nc, .skip
    ld b, a
.lit:
    ld a, (hl)
    cpl
    ex de, hl
    and (hl)
    ld (hl), a
    ex de, hl
    inc hl
    call advance
    djnz .lit
    jr .next
.zeros:
    sub #BF
    ld b, a
.zero:
    xor a
    ld (de), a
    call advance
    djnz .zero
    jr .next
.skip:
    sub #7F
    ld b, a
.sk:
    call advance
    djnz .sk
    jr .next

start:
    ld de, PF_PANEL_SCR
    ld c, PF_LW
    ret

; Steps DE one byte through the panel, wrapping to the start of the next
; pixel line after PF_LW bytes. C counts the bytes left on the line.
advance:
    inc e
    dec c
    ret nz
    ld a, e
    sub PF_LW
    ld e, a
    ld c, PF_LW
    inc d
    ld a, d
    and 7
    ret nz
    ld a, e
    add a, 32
    ld e, a
    ret c
    ld a, d
    sub 8
    ld d, a
    ret
