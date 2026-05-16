def pre_init_hook(cr):
    """Preserve manual invoice/CDP references when certificate_ref becomes computed."""
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sbu_estimate_sal_line' AND column_name = 'certificate_ref'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        ALTER TABLE sbu_estimate_sal_line
        ADD COLUMN IF NOT EXISTS _sbu_certificate_ref_manual VARCHAR
        """
    )
    cr.execute(
        """
        UPDATE sbu_estimate_sal_line
        SET _sbu_certificate_ref_manual = certificate_ref
        WHERE certificate_ref IS NOT NULL
          AND TRIM(certificate_ref) <> ''
          AND (_sbu_certificate_ref_manual IS NULL OR TRIM(_sbu_certificate_ref_manual) = '')
        """
    )
