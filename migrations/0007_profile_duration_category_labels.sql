INSERT INTO metadata.profile_categories (
    classifier, category_code, category_state, category_label
) VALUES
    ('working_time_duration', '2', 'valid', 'Less than 15 hours'),
    ('working_time_duration', '3', 'valid', '15 to 24 hours'),
    ('working_time_duration', '4', 'valid', '25 to 34 hours'),
    ('working_time_duration', '5', 'valid', '35 to 39 hours'),
    ('working_time_duration', '6', 'valid', '40 to 48 hours'),
    ('working_time_duration', '7', 'valid', '49 to 56 hours'),
    ('working_time_duration', '8', 'valid', 'More than 56 hours')
ON CONFLICT (classifier, category_code, category_state) DO UPDATE SET
    category_label = EXCLUDED.category_label;
