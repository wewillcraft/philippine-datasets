export interface PSGCData {
  psgc_code: string;
  name: string;
  correspondence_code: string;
  geographic_level: string;
  old_names: string | null;
  city_class: string | null;
  income_classification: string | null;
  urban_rural: string | null;
  population_2020: number | null;
  status: string | null;
  region_code: string;
  province_code: string;
  municipality_code: string;
  barangay_code: string;
  admin_level: string;
  is_region: boolean;
  is_province: boolean;
  is_city_municipality: boolean;
  is_barangay: boolean;
  is_submunicipality: boolean;
}

export interface Region {
  psgc_code: string;
  name: string;
  correspondence_code: string;
  population_2020?: number;
}

export interface Province {
  psgc_code: string;
  name: string;
  correspondence_code: string;
  population_2020?: number;
  region_code: string;
}

export interface CityMunicipality {
  psgc_code: string;
  name: string;
  correspondence_code: string;
  city_class?: string;
  income_classification?: string;
  population_2020?: number;
  region_code: string;
  province_code: string;
}

export interface Barangay {
  psgc_code: string;
  name: string;
  correspondence_code: string;
  urban_rural?: string;
  population_2020?: number;
  region_code: string;
  province_code: string;
  municipality_code: string;
}

export interface SubMunicipality {
  psgc_code: string;
  name: string;
  correspondence_code: string;
  population_2020?: number;
  region_code: string;
  province_code: string;
  municipality_code: string;
}
