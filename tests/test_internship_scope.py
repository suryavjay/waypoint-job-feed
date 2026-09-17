import unittest
from internship_pipeline.jobs import is_relevant
from internship_pipeline.sources.base import category_for, normalize


class InternshipScopeTests(unittest.TestCase):
    def test_mixed_and_permanent_titles_are_excluded(self):
        for title in ('Software Engineer New Grad 2027', 'Software Intern / New Grad',
                      'Software Engineering Intern or Full-Time', 'Full-time / Data Science Intern',
                      'Software Engineer Intern - Interns/Graduates', 'Permanent Software Intern'):
            with self.subTest(title=title):
                self.assertFalse(is_relevant(title))

    def test_student_and_full_time_hours_internships_remain(self):
        for title in ('Software Engineer Intern - Undergraduate', 'ML Graduate Research Intern',
                      'Full-Time Data Science Internship', 'Quantitative Trading Intern',
                      'Trader Intern', 'SWE Intern — Class of 2028', 'Software Engineering Internships'):
            with self.subTest(title=title):
                self.assertTrue(is_relevant(title))

    def test_actual_role_beats_combined_source_heading(self):
        for title, expected in (('Data Scientist Intern', 'Data'), ('Software Engineer Intern', 'SWE'),
                                ('Machine Learning Intern', 'ML / AI'), ('Trader Intern', 'Quant')):
            self.assertEqual(category_for(title, 'Data Science, AI & ML'), expected)

    def test_description_return_offer_is_not_a_permanent_role(self):
        job = normalize({'company': 'Example', 'title': 'Software Intern Summer 2027',
                         'description': 'Full-time internship. May lead to a new grad return offer. Graduation in 2028.',
                         'url': 'https://example.com/jobs/intern'},
                        source_key='fixture', source_name='Fixture', source_url='https://example.com')
        self.assertIsNotNone(job)


if __name__ == '__main__':
    unittest.main()
