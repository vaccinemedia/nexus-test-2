; photofit3.asm — bank 3 at #C000: draws the dossier face's facial hair and
; hair, between bank 4's two passes. Entered via photofit.asm.

    MODULE pf3
    ORG #C000

hair:
    ld a, (pf_sel + PF_FACIAL)
    ld hl, pfl_facial_tab
    call feature
    ld a, (pf_sel + PF_HAIR)
    ld hl, pfl_hair_tab
    jp feature

    INCLUDE "pf_dossier_draw.inc"
    INCLUDE "photofit_large_b.inc"
End:
    ASSERT End <= #10000, "photofit bank 3 is full"
    ENDMODULE
