const axios = require('axios');

const TRESTLE_API_KEY = process.env.TRESTLE_API_KEY;
const BASE_URL = 'https://api.trestleiq.com/3.1/location';

if (!TRESTLE_API_KEY) {
  console.error('Missing TRESTLE_API_KEY environment variable. Set it in your .env file.');
  process.exit(1);
}

async function lookupAddress({ street_line_1, city, state_code, postal_code }) {
  const params = { street_line_1, city, state_code, postal_code };

  console.log(`Looking up: ${street_line_1}, ${city}, ${state_code} ${postal_code}`);

  try {
    const response = await axios.get(BASE_URL, {
      params,
      headers: {
        'x-api-key': TRESTLE_API_KEY,
        'accept': 'application/json'
      }
    });

    const data = response.data;

    if (!data.residents || data.residents.length === 0) {
      console.log('No residents found for this address.');
      return [];
    }

    const results = data.residents.map(resident => ({
      name: resident.name || null,
      phones: (resident.phones || []).map(p => ({
        number: p.phone_number,
        type: p.line_type || 'unknown'
      })),
      emails: (resident.emails || []).map(e => e.email_address)
    }));

    return results;

  } catch (err) {
    if (err.response) {
      console.error(`Trestle API error ${err.response.status}: ${err.response.statusText}`);
      console.error('Response:', JSON.stringify(err.response.data, null, 2));
    } else if (err.request) {
      console.error('No response from Trestle API. Check your network connection.');
    } else {
      console.error('Request setup error:', err.message);
    }
    return null;
  }
}

module.exports = { lookupAddress };
